import json
from concurrent.futures import ThreadPoolExecutor
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
    def test_two_managers_serialize_start_for_same_root(self):
        # Manual and automatic entry points must share the registry lock.
        other = Manager(self.root)
        barrier = threading.Barrier(2)
        def start(manager):
            barrier.wait(timeout=5)
            return manager.start(self.service)
        with patch.object(Manager, 'healthy', return_value=False):
            with ThreadPoolExecutor(max_workers=2) as pool:
                tasks = [pool.submit(start, manager) for manager in (self.manager, other)]
                results = [task.result(timeout=10) for task in tasks]
        try:
            self.assertEqual(sum('已发出启动命令' in value for value in results), 1)
            self.assertEqual(sum('进程已运行' in value for value in results), 1)
            self.assertEqual(len(self.manager.records()), 1)
        finally:
            # Reap the Popen handle regardless of which manager won the race.
            owner = self.manager if self.service['id'] in self.manager.handles else other
            owner.stop(self.service)
    def test_reject_invalid_service_name(self):
        (self.root/'services.json').write_text(json.dumps({'services':[{'id':'../bad','command':[]}]}))
        with self.assertRaises(ValueError):load_services(self.root)

if __name__=='__main__':unittest.main()
