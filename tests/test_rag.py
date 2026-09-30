import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
import rag_server as rag

class RagTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.docs=self.root/'documents'; self.docs.mkdir()
        self.patches=[patch.object(rag,'DB_PATH',self.root/'kb.db'),patch.object(rag,'DOCUMENTS_DIR',self.docs)]
        for p in self.patches:p.start()
        self.client=TestClient(rag.app,base_url='http://127.0.0.1')

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def test_chunk_bounds_and_no_text_loss(self):
        text='abc中文'*1500
        chunks=rag.split_chunks(text)
        self.assertTrue(all(0<len(c)<=rag.CHUNK_SIZE for c in chunks))
        rebuilt=chunks[0]+''.join(c[rag.CHUNK_OVERLAP:] for c in chunks[1:])
        self.assertEqual(rebuilt,text)
        self.assertEqual(rag.split_chunks('短文'),['短文'])

    def test_chinese_bm25(self):
        scores=rag.bm25_scores('模型目录',['天气晴朗','模型目录位于本地'])
        self.assertGreater(scores[1],scores[0])

    def test_origin_and_host(self):
        self.assertEqual(self.client.get('/ready').status_code,200)
        self.assertEqual(self.client.get('/ready',headers={'Host':'evil.invalid'}).status_code,400)
        self.assertEqual(self.client.post('/ingest',headers={'Origin':'https://evil.invalid'},json={'path':'documents'}).status_code,403)

    def test_outside_document_root(self):
        outside=self.root/'private.txt'; outside.write_text('not importable')
        self.assertEqual(self.client.post('/ingest',json={'path':str(outside)}).status_code,403)

    def test_import_reimport_query(self):
        doc=self.docs/'hello.txt'; doc.write_text('模型资料存放在用户配置的 documents 文件夹。',encoding='utf-8')
        def vectors(texts):return [np.array([1.,0.],dtype=np.float32) for _ in texts]
        with patch.object(rag,'embed_texts',side_effect=vectors):
            result=self.client.post('/ingest',json={'path':str(doc)}).json()
            self.assertEqual(result['indexed_files'],1)
            self.assertEqual(self.client.post('/ingest',json={'path':str(doc)}).json()['indexed_files'],0)
            with patch.object(rag,'rerank',side_effect=lambda q,rows,k:[{'row':rows[0],'score':.9}]),patch.object(rag,'generate_answer',return_value='资料在 documents。[S1]'):
                answer=self.client.post('/query',json={'question':'资料在哪里？'}).json()
                self.assertIn('[S1]',answer['answer'])
                self.assertEqual(answer['sources'][0]['id'],'S1')

    def test_failed_reimport_preserves_existing(self):
        doc=self.docs/'hello.txt';doc.write_text('Original document',encoding='utf-8')
        with patch.object(rag,'embed_texts',return_value=[np.array([1.,0.],dtype=np.float32)]):
            self.client.post('/ingest',json={'path':str(doc)})
        doc.write_text('Updated document',encoding='utf-8')
        with patch.object(rag,'embed_texts',side_effect=RuntimeError('offline')):
            result=self.client.post('/ingest',json={'path':str(doc)}).json()
            self.assertEqual(len(result['skipped']),1)
        with rag.connect_db() as db:
            self.assertEqual(db.execute('SELECT content FROM chunks').fetchone()[0],'Original document')

    def test_empty_collection(self):
        self.assertEqual(self.client.post('/query',json={'question':'test','generate':False}).status_code,404)

if __name__=='__main__':unittest.main()
