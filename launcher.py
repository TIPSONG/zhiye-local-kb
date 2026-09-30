"""Chinese desktop launcher. Stop controls remain usable during startup."""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import webbrowser
from service_manager import Manager, ROOT, load_services

class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('知页 · 本地知识工作台')
        self.geometry('1000x700')
        self.minsize(850,600)
        self.configure(bg='#111820')
        self.manager=Manager()
        self.services=load_services()
        self.events=queue.Queue()
        self.cancel=threading.Event()
        self.starting=False
        self.stopping=False
        self.checking=False
        self.rows={}
        style=ttk.Style(self); style.theme_use('clam')
        style.configure('TButton',font=('Microsoft YaHei UI',10),padding=8)
        tk.Label(self,text='知页 / LOCAL KNOWLEDGE',bg='#111820',fg='#70dfb0',font=('Microsoft YaHei UI',22,'bold')).pack(anchor='w',padx=24,pady=(24,8))
        tk.Label(self,text='资料问答 · 模型管理 · 可选 Agent 记忆',bg='#111820',fg='#9baebf',font=('Microsoft YaHei UI',11)).pack(anchor='w',padx=24)
        bar=tk.Frame(self,bg='#111820'); bar.pack(fill='x',padx=24,pady=18)
        self.start_button=ttk.Button(bar,text='启动已启用服务',command=lambda:self.start(self.services)); self.start_button.pack(side='left')
        ttk.Button(bar,text='游戏模式 · 释放模型',command=lambda:self.stop([s for s in self.services if s['group']=='model'])).pack(side='left',padx=8)
        ttk.Button(bar,text='关闭全部已管理服务',command=lambda:self.stop(self.services)).pack(side='left')
        ttk.Button(bar,text='刷新状态',command=self.refresh).pack(side='right')
        table=tk.Frame(self,bg='#1b2531',padx=14,pady=10); table.pack(fill='x',padx=24)
        table.grid_columnconfigure(0,weight=1)
        for index,service in enumerate(self.services):
            tk.Label(table,text=service['label'],bg='#1b2531',fg='#eef4fa',font=('Microsoft YaHei UI',11)).grid(row=index,column=0,sticky='w',pady=10)
            label=tk.Label(table,text='检查中',bg='#1b2531',fg='#9baebf'); label.grid(row=index,column=1,padx=12)
            self.rows[service['id']]=label
            ttk.Button(table,text='启动',command=lambda s=service:self.start([s])).grid(row=index,column=2,padx=4)
            ttk.Button(table,text='关闭',command=lambda s=service:self.stop([s])).grid(row=index,column=3,padx=4)
            if service.get('open_url'):
                ttk.Button(table,text='打开网页',command=lambda s=service:webbrowser.open(s['open_url'])).grid(row=index,column=4,padx=4)
        tk.Label(self,text='修改 services.json 后重开启动台。关闭窗口不停止后台服务。',bg='#111820',fg='#9baebf').pack(anchor='w',padx=24,pady=(14,8))
        self.log=tk.Text(self,bg='#0b1118',fg='#c6d8e6',relief='flat',height=8,state='disabled',wrap='word')
        self.log.pack(fill='both',expand=True,padx=24,pady=(0,20))
        self.after(100,self.drain); self.after(200,self.refresh); self.after(5000,self.periodic)

    def drain(self):
        while not self.events.empty():
            event,value=self.events.get_nowait()
            if event=='log':
                self.log.configure(state='normal'); self.log.insert('end',value+'\n'); self.log.see('end'); self.log.configure(state='disabled')
            elif event=='started': self.starting=False; self.start_button.state(['!disabled'])
            elif event=='stopped': self.stopping=False
            elif event=='health':
                self.checking=False
                for key,ready in value.items(): self.rows[key].configure(text='● 已就绪' if ready else '○ 未就绪',fg='#70dfb0' if ready else '#e8b678')
        self.after(100,self.drain)

    def refresh(self):
        if self.checking:return
        self.checking=True
        def check(): self.events.put(('health',{s['id']:self.manager.healthy(s) for s in self.services}))
        threading.Thread(target=check,daemon=True).start()

    def periodic(self): self.refresh(); self.after(5000,self.periodic)

    def start(self,services):
        if self.starting or self.stopping:return
        self.starting=True; self.cancel.clear(); self.start_button.state(['disabled'])
        def run():
            try:
                for service in services:
                    if self.cancel.is_set():break
                    try:self.events.put(('log',service['label']+'：'+self.manager.start(service,self.cancel)))
                    except Exception as error:self.events.put(('log',service['label']+'：'+str(error)))
            finally:self.events.put(('started',None))
        threading.Thread(target=run,daemon=True).start()

    def stop(self,services):
        if self.stopping:return
        if not messagebox.askyesno('确认关闭','将取消待执行的启动操作，并停止选中的已登记服务。\n进行中的生成、索引或记忆写入可能中断。\n不会删除资料；不会停止启动台之外运行的进程。',default='no'):return
        self.cancel.set(); self.stopping=True
        def run():
            try:
                # Stop apps before their model dependencies.
                for service in sorted(services,key=lambda s:s['group']=='model'):
                    try:self.events.put(('log',service['label']+'：'+self.manager.stop(service)))
                    except Exception as error:self.events.put(('log',service['label']+'：'+str(error)))
            finally:self.events.put(('stopped',None))
        threading.Thread(target=run,daemon=True).start()

if __name__=='__main__':
    try:
        app=Launcher()
        if '--smoke-test' in sys.argv:app.after(1500,app.destroy)
        app.mainloop()
    except Exception as error:
        messagebox.showerror('启动台错误',str(error))
        raise
