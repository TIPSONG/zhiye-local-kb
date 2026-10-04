"""Portable desktop workbench. Service ownership remains in service_manager."""
import concurrent.futures
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
import webbrowser

import desktop_ui as ui
from service_manager import Manager, ROOT, load_services


class Launcher(tk.Tk):
    def __init__(self, root=ROOT, services=None, manager=None, auto_refresh=True, demo=False):
        super().__init__()
        self.demo = demo
        self.root_path = Path(root)
        self.manager = manager if manager is not None else (None if demo else Manager(self.root_path))
        self.services = load_services(self.root_path) if services is None else services
        self.model_services = [s for s in self.services if s.get('group') == 'model']
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.starting = self.stopping = self.checking = False
        self.start_buttons, self.stop_buttons = [], []
        self.timers = set()
        ui.build(self)
        self.write('界面预览：使用示例配置，不探测、不启动、不关闭真实服务。' if demo
                   else '工作台已打开。只管理本工作台登记的进程；外部服务不会被接管。')
        self.schedule(100, self.drain)
        if demo:
            ui.update_status(self, {})
        elif auto_refresh:
            self.schedule(200, self.refresh)
            self.schedule(5000, self.periodic)
        self.protocol('WM_DELETE_WINDOW', self.close_window)

    def schedule(self, delay, callback):
        token = None
        def run():
            self.timers.discard(token)
            callback()
        token = self.after(delay, run)
        self.timers.add(token)

    def close_window(self):
        # Deliberately leave launched services alone.
        for token in list(self.timers):
            self.after_cancel(token)
        self.timers.clear()
        # Release Tk-owned images on the UI thread, before destroying the interpreter.
        self.brand_icon = None
        self.destroy()

    def write(self, value):
        self.log.configure(state='normal')
        self.log.insert('end', time.strftime('%H:%M:%S  ') + value.rstrip() + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')
        lines = value.strip().splitlines()
        if lines: self.activity.configure(text=lines[-1][:75])

    def drain(self):
        while not self.events.empty():
            event, value = self.events.get_nowait()
            if event == 'log':
                self.write(value)
            elif event == 'started':
                self.starting = False
                ui.update_busy(self)
                self.refresh()
            elif event == 'stopped':
                self.stopping = False
                ui.update_busy(self)
                self.refresh()
            elif event == 'health':
                self.checking = False
                ui.update_status(self, value)
        self.schedule(100, self.drain)

    def refresh(self):
        if self.demo:
            ui.update_status(self, {})
            return
        if self.checking: return
        self.checking = True
        def check():
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                    values = dict(zip((s['id'] for s in self.services),
                                      pool.map(self.manager.healthy, self.services)))
            except Exception as error:
                self.events.put(('log', f'状态检查失败：{error}'))
                values = {}
            self.events.put(('health', values))
        threading.Thread(target=check, daemon=True).start()

    def periodic(self):
        self.refresh()
        self.schedule(5000, self.periodic)

    def start(self, services):
        if self.demo:
            self.write('界面预览不会启动服务。')
            return
        if self.starting or self.stopping: return
        self.starting = True
        self.cancel.clear()
        ui.update_busy(self)
        def run():
            try:
                for service in services:
                    if self.cancel.is_set(): break
                    try: result = self.manager.start(service, self.cancel)
                    except Exception as error: result = str(error)
                    self.events.put(('log', service['label'] + '：' + result))
            finally: self.events.put(('started', None))
        threading.Thread(target=run, daemon=True).start()

    def stop(self, services):
        if self.demo:
            self.write('界面预览不会关闭服务。')
            return
        if self.stopping: return
        if not services:
            self.write('没有匹配的已配置服务。')
            return
        if not messagebox.askyesno('确认关闭',
                '将取消待执行的启动操作，并停止选中的已登记服务。\n'
                '进行中的生成、索引或记忆写入可能中断。\n'
                '不会删除资料；不会关闭工作台之外启动的进程。', default='no', parent=self):
            return
        self.cancel.set()
        self.stopping = True
        ui.update_busy(self)
        def run():
            try:
                for service in sorted(services, key=lambda s: s.get('group') == 'model'):
                    try: result = self.manager.stop(service)
                    except Exception as error: result = str(error)
                    self.events.put(('log', service['label'] + '：' + result))
            finally: self.events.put(('stopped', None))
        threading.Thread(target=run, daemon=True).start()

    def open_service(self, service):
        if self.demo:
            self.write('界面预览不会打开外部页面。')
            return
        # Config URLs have already been restricted to localhost by load_services.
        if service.get('open_url'): webbrowser.open(service['open_url'])

    def open_path(self, path):
        if self.demo:
            self.write('界面预览不会打开本地文件。')
            return
        path = Path(path)
        if not path.exists():
            messagebox.showinfo('文件或目录尚不存在', f'没有找到：\n{path}\n请先运行 setup.ps1 或创建对应目录。', parent=self)
            return
        if os.name == 'nt': os.startfile(path)
        else: subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)])

    def copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self.log.get('1.0', 'end-1c'))
        self.activity.configure(text='已复制；分享前请检查记录中的路径和错误信息。')


if __name__ == '__main__':
    preview = '--demo' in sys.argv or '--smoke-test' in sys.argv
    # Demo uses only the distributable template, never a user's services.json.
    if preview:
        import json
        services = json.loads((ROOT/'services.example.json').read_text(encoding='utf-8'))['services']
    else:
        services = None
    try:
        app = Launcher(services=services, demo=preview)
        if '--smoke-test' in sys.argv:
            app.schedule(1500, app.close_window)
        app.mainloop()
    except Exception as error:
        if sys.stderr is not None: print(f'工作台无法启动：{error}', file=sys.stderr)
        raise
