import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from service_manager import Manager,load_services

class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.manager=Manager(self.root)
        self.service={'id':'fixture','enabled':True,'command':[sys.executable,'-c','import time; time.sleep(60)']}
    def tearDown(self):
        self.manager.stop(self.service)
        self.temp.cleanup()
    def test_external_not_owned(self):
        with patch.object(self.manager,'healthy',return_value=True):
            self.assertIn('外部',self.manager.start(self.service))
        self.assertEqual(self.manager.records(),{})
        self.assertIn('不会关闭',self.manager.stop(self.service))
    def test_cancel_before_spawn(self):
        cancel=threading.Event();cancel.set()
        self.assertIn('取消',self.manager.start(self.service,cancel))
        self.assertFalse(self.manager.records())
    def test_real_start_stop(self):
        self.manager.start(self.service)
        record=self.manager.records()['fixture']
        self.assertIsNotNone(self.manager.owned(record))
        tampered=dict(record,created=record['created']-10)
        self.assertIsNone(self.manager.owned(tampered))
        self.manager.stop(self.service)
        self.assertIsNone(self.manager.owned(record))
    def test_reject_invalid_service_name(self):
        (self.root/'services.json').write_text(json.dumps({'services':[{'id':'../bad','command':[]}]}))
        with self.assertRaises(ValueError):load_services(self.root)

if __name__=='__main__':unittest.main()
