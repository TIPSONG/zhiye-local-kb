"""Portable process ownership and direct-to-file logs; no inherited stdout pipes."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlparse
import httpx
import psutil
from filelock import FileLock

ROOT = Path(__file__).resolve().parent

def load_services(root=ROOT):
    path = root / 'services.json'
    if not path.exists(): path = root / 'services.example.json'
    services = json.loads(path.read_text(encoding='utf-8'))['services']
    seen = set()
    for service in services:
        key = service['id']
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', key) or key in seen:
            raise ValueError('Service ids must be unique lowercase identifiers')
        seen.add(key)
        for command_field in ('command', 'stop_command'):
            args = service.get(command_field, [])
            if not isinstance(args, list) or not all(isinstance(a,str) and a for a in args):
                raise ValueError(f'{key}: {command_field} must be an argument list, not a shell string')
        for field in ['health_url','open_url']:
            url = service.get(field)
            if url and (urlparse(url).scheme != 'http' or urlparse(url).hostname not in ('127.0.0.1','localhost','::1')):
                raise ValueError(f'{key}: only local HTTP service URLs are allowed')
    return services

class Manager:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.runtime = self.root / 'runtime'
        self.runtime.mkdir(exist_ok=True)
        self.registry = self.runtime / 'processes.json'
        self.lock = FileLock(str(self.runtime / 'manager.lock'), timeout=60)
        self.handles = {}

    def records(self):
        return json.loads(self.registry.read_text(encoding='utf-8')) if self.registry.exists() else {}

    def save(self, records):
        temp = self.registry.with_suffix('.tmp')
        temp.write_text(json.dumps(records, indent=2), encoding='utf-8')
        temp.replace(self.registry)

    @staticmethod
    def owned(record):
        try:
            proc = psutil.Process(record['pid'])
            if (abs(proc.create_time()-record['created']) < .01 and
                proc.exe() == record['exe'] and proc.cmdline() == record['cmdline']):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied): pass
        return None

    @staticmethod
    def healthy(service):
        try:
            with httpx.Client(timeout=2,trust_env=False) as client:
                response = client.get(service['health_url'])
                return response.status_code == 200
        except (httpx.HTTPError,KeyError): return False

    def start(self, service, cancel=None):
        with self.lock:
            if cancel and cancel.is_set(): return '已取消启动'
            records = self.records()
            current = records.get(service['id'])
            if current and self.owned(current): return '进程已运行'
            if self.healthy(service): return '检测到外部服务；不会接管或停止它'
            if not service.get('enabled') or not service.get('command'): return '未启用 / 未配置启动命令'
            args = [x.replace('{python}',sys.executable).replace('{root}',str(self.root)) for x in service['command']]
            log_path = self.runtime / (service['id']+'.log')
            with log_path.open('ab',buffering=0) as log:
                process = subprocess.Popen(args,cwd=service.get('cwd',str(self.root)),
                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,close_fds=True,
                    env=dict(os.environ,PYTHONUTF8='1'),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                    start_new_session=os.name!='nt')
            try:
                proc=psutil.Process(process.pid)
                records[service['id']]={'pid':proc.pid,'created':proc.create_time(),'exe':proc.exe(),'cmdline':proc.cmdline()}
                self.save(records)
                self.handles[service['id']] = process
            except (psutil.NoSuchProcess,psutil.AccessDenied):
                # Do not leave an untracked process after registration failure.
                if process.poll() is None: process.terminate()
                process.wait(timeout=10)
                raise RuntimeError(f'无法登记进程；检查 {log_path.name}')
            return '已发出启动命令（就绪状态会另行刷新）'

    def stop(self, service):
        with self.lock:
            records=self.records()
            record=records.get(service['id'])
            if not record: return '未登记：不会关闭外部进程'
            proc=self.owned(record)
            if not proc:
                records.pop(service['id']); self.save(records)
                return '登记已过期，未停止任何进程'
            if service.get('stop_command'):
                args=[x.replace('{python}',sys.executable).replace('{root}',str(self.root)) for x in service['stop_command']]
                subprocess.run(args,cwd=service.get('cwd',str(self.root)),check=True,timeout=45,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                proc.wait(timeout=10)
            else:
                # Snapshot only this verified process's descendants, never process names/ports.
                children=proc.children(recursive=True)
                for child in reversed(children):
                    try: child.terminate()
                    except psutil.NoSuchProcess: pass
                try: proc.terminate()
                except psutil.NoSuchProcess: pass
                _,alive=psutil.wait_procs(children+[proc],timeout=10)
                if alive: raise RuntimeError('进程尚未退出；未自动强制结束，请查看系统任务管理器')
            records.pop(service['id']); self.save(records)
            handle = self.handles.pop(service['id'], None)
            if handle is not None: handle.wait(timeout=10)
            return '已关闭，文件和数据保留'
