"""Dependency-free desktop presentation; service actions stay in launcher.py."""
import os
import time
import tkinter as tk
from tkinter import ttk, messagebox

BG = '#F4F5F2'
WHITE = '#FFFFFF'
INK = '#202B29'
MUTED = '#76817D'
LINE = '#E2E7E2'
GREEN = '#23745B'
SIDEBAR = '#192823'
FONT = 'Microsoft YaHei UI'


def text(parent, value='', size=10, color=INK, bold=False, **kw):
    return tk.Label(parent, text=value, bg=parent.cget('bg'), fg=color,
                    font=(FONT, size, 'bold' if bold else 'normal'), **kw)


class Surface(tk.Canvas):
    """Rounded, resize-aware native card with ordinary accessible child widgets."""
    def __init__(self, parent, fill=WHITE, radius=16, padding=20, **kw):
        super().__init__(parent, bg=parent.cget('bg'), highlightthickness=0,
                         bd=0, **kw)
        self.fill, self.radius, self.padding = fill, radius, padding
        self.body = tk.Frame(self, bg=fill)
        self.slot = self.create_window(padding, padding, window=self.body, anchor='nw')
        self.bind('<Configure>', self.resize)

    def resize(self, event):
        w, h, r, p = event.width, event.height, self.radius, self.padding
        self.delete('surface')
        self.create_polygon(r, 0, w-r, 0, w, 0, w, r, w, h-r, w, h,
                            w-r, h, r, h, 0, h, 0, h-r, 0, r, 0, 0,
                            smooth=True, splinesteps=24, fill=self.fill,
                            outline='', tags='surface')
        self.tag_lower('surface')
        self.itemconfigure(self.slot, width=max(1, w-2*p), height=max(1, h-2*p))


def icon(parent, kind, fill='#E8F2EB', stroke=GREEN, size=42):
    c = tk.Canvas(parent, width=size, height=size, bg=parent.cget('bg'),
                  highlightthickness=0)
    c.create_oval(1, 1, size-1, size-1, fill=fill, outline='')
    if kind in ('book', 'file'):
        c.create_rectangle(14, 10, 29, 31, outline=stroke, width=2)
        for y in (16, 21, 26): c.create_line(18, y, 25, y, fill=stroke, width=2)
        if kind == 'book': c.create_line(11, 13, 11, 33, 27, 33, fill=stroke, width=2)
    elif kind == 'graph':
        for x, y in ((13, 14), (29, 13), (22, 29)):
            c.create_line(21, 20, x, y, fill=stroke, width=2)
            c.create_oval(x-3, y-3, x+3, y+3, fill=fill, outline=stroke, width=2)
    elif kind == 'search':
        c.create_oval(11, 10, 27, 26, outline=stroke, width=2)
        c.create_line(25, 24, 32, 31, fill=stroke, width=3)
    else:
        c.create_rectangle(13, 13, 29, 29, outline=stroke, width=2)
        for n in (17, 25):
            c.create_line(n, 8, n, 13, fill=stroke, width=2)
            c.create_line(n, 29, n, 34, fill=stroke, width=2)
            c.create_line(8, n, 13, n, fill=stroke, width=2)
            c.create_line(29, n, 34, n, fill=stroke, width=2)
    return c


class ScrollArea(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, bd=0, highlightthickness=0)
        bar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        bar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=bar.set)
        self.body = tk.Frame(self.canvas, bg=BG)
        item = self.canvas.create_window(0, 0, anchor='nw', window=self.body)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(item, width=e.width))
        self.body.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))


def action(app, parent, caption, callback, kind='Soft', role=None):
    b = ttk.Button(parent, text=caption, command=callback, style=kind+'.TButton', cursor='hand2')
    if role == 'start': app.start_buttons.append(b)
    elif role == 'stop': app.stop_buttons.append(b)
    return b


def badge_state(service, ready):
    if ready: return '● 接口就绪', GREEN
    if not service.get('enabled') or not service.get('command'):
        return '○ 未启用', MUTED
    return '○ 未就绪', '#A28554'


def build(app):
    app.title('知页 · 本地知识工作台' + (' · 界面预览' if app.demo else ''))
    app.geometry('1320x860')
    app.minsize(1120, 780)
    app.configure(bg=BG)
    app.option_add('*Font', (FONT, 10))
    app.brand_icon = tk.PhotoImage(width=32, height=32)
    app.brand_icon.put(GREEN, to=(0, 0, 32, 32))
    app.brand_icon.put('#DBECC5', to=(8, 6, 24, 26))
    for y in (11, 16, 21): app.brand_icon.put(GREEN, to=(12, y, 21, y+2))
    app.iconphoto(True, app.brand_icon)
    style = ttk.Style(app)
    style.theme_use('clam')
    for name, bg, fg, hover in [('Primary', GREEN, WHITE, '#185D48'),
            ('Soft', '#EFF3EE', '#3E554B', '#DFE9DF'),
            ('Ghost', WHITE, '#65716B', '#F2F4EF'),
            ('Danger', '#FAEEE9', '#AD5945', '#F4DFD6'),
            ('Hero', '#D9EDBC', '#263E2E', '#C5E2A0')]:
        style.configure(name+'.TButton', background=bg, foreground=fg, borderwidth=0,
                        padding=(14, 9), font=(FONT, 10))
        style.map(name+'.TButton', background=[('disabled', '#E9EDE8'), ('active', hover)],
                  foreground=[('disabled', '#9AA49D')])
    style.configure('Horizontal.TProgressbar', background=GREEN, troughcolor=LINE, borderwidth=0)
    app.nav, app.pages, app.rows, app.cards = {}, {}, {}, []
    sidebar = tk.Frame(app, bg=SIDEBAR, width=208)
    sidebar.pack(side='left', fill='y'); sidebar.pack_propagate(False)
    logo = tk.Frame(sidebar, bg=SIDEBAR); logo.pack(fill='x', padx=24, pady=(32, 34))
    icon(logo, 'book', '#CEE7B3', '#294537').pack(side='left', padx=(0, 10))
    text(logo, '知页', 23, '#F0F5EC', True).pack(anchor='w')
    text(logo, 'LOCAL WORKSPACE', 8, '#9BAEA3').pack(anchor='w')
    text(sidebar, '工作空间', 9, '#7E9588').pack(anchor='w', padx=28, pady=(0, 12))
    for key, label in [('overview', '◫   工作台'), ('models', '▦   模型管理'),
                       ('files', '▤   文件与目录'), ('logs', '≡   运行记录')]:
        b = tk.Button(sidebar, text=label, anchor='w', command=lambda k=key: show(app, k),
                      bg=SIDEBAR, fg='#ABBDB2', activebackground='#30463A',
                      activeforeground=WHITE, bd=0, padx=18, pady=13,
                      cursor='hand2', font=(FONT, 11), takefocus=True)
        b.pack(fill='x', padx=14, pady=3); app.nav[key] = b
    foot = tk.Frame(sidebar, bg=SIDEBAR); foot.pack(side='bottom', fill='x', padx=26, pady=28)
    text(foot, '●  本机工作空间', 10, '#BDDBA8', True).pack(anchor='w')
    text(foot, '仅管理自己启动的进程\n关闭窗口不停止后台服务', 9, '#82998C', justify='left').pack(anchor='w', pady=(10, 0))
    main = tk.Frame(app, bg=BG); main.pack(side='left', fill='both', expand=True)
    header = tk.Frame(main, bg=BG); header.pack(fill='x', padx=30, pady=(24, 18))
    left = tk.Frame(header, bg=BG); left.pack(side='left')
    text(left, 'WORKSPACE  /  本地服务', 9, MUTED).pack(anchor='w')
    app.page_title = text(left, '工作台', 24, INK, True); app.page_title.pack(anchor='w', pady=(4, 0))
    action(app, header, '启动已启用服务  ↗', lambda: app.start(app.services), 'Primary', 'start').pack(side='right', padx=(10, 0))
    action(app, header, '刷新状态', app.refresh).pack(side='right')
    container = tk.Frame(main, bg=BG); container.pack(fill='both', expand=True, padx=30)
    for key in app.nav: app.pages[key] = tk.Frame(container, bg=BG)
    overview(app, app.pages['overview'])
    models(app, app.pages['models'])
    files(app, app.pages['files'])
    logs(app, app.pages['logs'])
    footer = tk.Frame(main, bg=BG); footer.pack(fill='x', padx=30, pady=(12, 18))
    app.activity = text(footer, '正在检查服务状态…', 9, MUTED, anchor='w')
    app.activity.pack(side='left', fill='x', expand=True)
    action(app, footer, '查看运行记录  →', lambda: show(app, 'logs')).pack(side='right')
    app.progress = ttk.Progressbar(main, mode='indeterminate')
    show(app, 'overview')


def service_card(app, parent, service, index):
    card = Surface(parent, height=214, padding=18)
    card.grid(row=index//2, column=index%2, sticky='nsew',
              padx=(0, 8) if index%2 == 0 else (8, 0), pady=(0, 16))
    app.cards.append(card)
    body = card.body
    top = tk.Frame(body, bg=WHITE); top.pack(fill='x')
    glyph = 'graph' if service['id']=='hindsight' else ('book' if service.get('group')=='app' else 'search')
    icon(top, glyph).pack(side='left', padx=(0, 12))
    names = tk.Frame(top, bg=WHITE); names.pack(side='left', fill='x', expand=True)
    title = text(names, service['label'], 14, INK, True, anchor='w')
    title.pack(fill='x')
    title.bind('<Configure>', lambda e: title.configure(wraplength=max(100,e.width)))
    text(names, service['id'].upper(), 8, MUTED).pack(anchor='w')
    badge = text(top, '○ 检测中', 9, MUTED); badge.pack(side='right')
    app.rows[service['id']] = badge
    desc = service.get('description', '按 services.json 配置连接和管理此服务。')
    label = text(body, desc, 10, MUTED, anchor='w', justify='left'); label.pack(fill='x', pady=(12, 0))
    label.bind('<Configure>', lambda e: label.configure(wraplength=max(150,e.width-4)))
    bar = tk.Frame(body, bg=WHITE); bar.pack(side='bottom', fill='x', pady=(12, 0))
    if service.get('open_url'):
        action(app, bar, '打开应用  ↗', lambda: app.open_service(service)).pack(side='left')
    action(app, bar, '启动', lambda: app.start([service]), 'Ghost', 'start').pack(side='left', padx=5)
    action(app, bar, '关闭', lambda: app.stop([service]), 'Ghost', 'stop').pack(side='right')


def overview(app, parent):
    hero = Surface(parent, fill='#E5ECD9', height=120, padding=22); hero.pack(fill='x', pady=(0, 18))
    right = tk.Frame(hero.body, bg='#E5ECD9'); right.pack(side='right', padx=(12, 0))
    action(app, right, '游戏模式 · 释放模型', lambda: app.stop(app.model_services), 'Hero', 'stop').pack(anchor='e')
    text(right, '只停止已登记模型，不删除资料', 9, '#76846A').pack(anchor='e', pady=(8, 0))
    text(hero.body, '把资料，变成随时可用的知识。', 18, '#304534', True).pack(anchor='w')
    app.hero_summary = text(hero.body, '正在检查本机接口…', 10, '#6A7D61'); app.hero_summary.pack(anchor='w', pady=(12, 0))
    section = tk.Frame(parent, bg=BG); section.pack(fill='x', pady=(0, 12))
    text(section, '你的应用', 12, INK, True).pack(side='left')
    text(section, '文档、检索与记忆各司其职', 9, MUTED).pack(side='right')
    area = ScrollArea(parent); area.pack(fill='both', expand=True)
    app.overview_area = area
    for n in range(2): area.body.grid_columnconfigure(n, weight=1, uniform='cards')
    services = [s for s in app.services if s.get('group')!='model']
    for i, service in enumerate(services): service_card(app, area.body, service, i)
    # Informational card only: the portable project does not ship a private parser script.
    info = Surface(area.body, height=214, padding=18)
    info.grid(row=len(services)//2, column=len(services)%2, sticky='nsew',
              padx=(0,8) if len(services)%2==0 else (8,0), pady=(0,16))
    text(info.body, 'OmniDocs 文档解析', 14, INK, True).pack(anchor='w')
    text(info.body, 'OPTIONAL INTEGRATION', 8, MUTED).pack(anchor='w', pady=(4,10))
    text(info.body, '扫描件先解析成 Markdown，再导入知页。\n本仓库不自动安装解析器或模型。', 10, MUTED, justify='left').pack(anchor='w')
    action(app, info.body, '查看接入说明  →', lambda: app.open_path(app.root_path/'docs'/'integrations.md')).pack(side='bottom', anchor='w')
    bottom = tk.Frame(parent, bg=BG); bottom.pack(fill='x', pady=(8, 0))
    text(bottom, '接口就绪不等于空闲；关闭前请结束其他客户端任务。', 9, MUTED).pack(side='left')
    action(app, bottom, '关闭全部已管理服务', lambda: app.stop(app.services), 'Danger', 'stop').pack(side='right')


def models(app, parent):
    text(parent, '共享模型', 17, INK, True).pack(anchor='w')
    text(parent, '状态只代表接口可用性。外部启动的模型不会被接管或关闭。', 10, MUTED).pack(anchor='w', pady=(8, 20))
    area = ScrollArea(parent); area.pack(fill='both', expand=True)
    if not app.model_services: text(area.body, '尚未配置模型服务。请编辑 services.json。', 11, MUTED).pack(anchor='w')
    for service in app.model_services:
        card = Surface(area.body, height=134, padding=20); card.pack(fill='x', pady=(0, 14))
        body = card.body
        icon(body, 'chip').pack(side='left', padx=(0, 16))
        ops = tk.Frame(body, bg=WHITE); ops.pack(side='right')
        label = text(ops, '○ 检测中', 9, MUTED); label.pack(anchor='e', pady=(0, 6))
        app.rows[service['id']] = label
        controls = tk.Frame(ops, bg=WHITE); controls.pack()
        action(app, controls, '启动', lambda s=service: app.start([s]), 'Soft', 'start').pack(side='left', padx=6)
        action(app, controls, '单独关闭', lambda s=service: app.stop([s]), 'Danger', 'stop').pack(side='left')
        info = tk.Frame(body, bg=WHITE); info.pack(side='left', fill='both', expand=True)
        for value, size, color in [(service['label'],14,INK), (service.get('description','通过配置的本机接口提供模型服务。'),10,MUTED),
                                    (service.get('health_url','未配置状态检查地址'),9,GREEN)]:
            label = text(info, value, size, color, anchor='w'); label.pack(fill='x', pady=(0,5))
            label.bind('<Configure>', lambda e,w=label: w.configure(wraplength=max(120,e.width)))
    action(app, parent, '释放全部已管理模型 · 游戏模式', lambda: app.stop(app.model_services), 'Primary', 'stop').pack(anchor='w', pady=(12,0))


def files(app, parent):
    text(parent, '文件与配置', 17, INK, True).pack(anchor='w')
    text(parent, '打开目录或配置文件，不移动或删除数据。修改服务配置后重新打开工作台。', 10, MUTED).pack(anchor='w', pady=(8, 20))
    area = ScrollArea(parent); area.pack(fill='both', expand=True)
    for title, relative, desc in [('文档目录','documents','默认导入目录；如设置 RAG_DOCUMENTS_DIR，请使用你配置的位置。'),
            ('模型目录','models','默认示例权重目录；自定义模型路径以 services.json 为准。'),
            ('运行日志','runtime','按服务保存日志与进程登记信息，不建议公开分享。'),
            ('服务配置','services.json','配置启动命令和本机接口；首次使用请运行 setup.ps1。')]:
        card=Surface(area.body,height=120);card.pack(fill='x',pady=(0,14))
        action(app,card.body,'打开  ↗',lambda p=app.root_path/relative:app.open_path(p)).pack(side='right')
        text(card.body,title,14,INK,True).pack(anchor='w')
        text(card.body,desc,9,MUTED).pack(anchor='w',pady=(7,4))
        text(card.body,relative,9,GREEN).pack(anchor='w')


def logs(app, parent):
    top=tk.Frame(parent,bg=BG);top.pack(fill='x',pady=(0,16))
    text(top,'本次运行记录',17,INK,True).pack(side='left')
    action(app,top,'复制记录',lambda:app.copy_log()).pack(side='right')
    text(parent,'这里只显示工作台操作。模型详细输出请查看 runtime 内对应服务的日志。',10,MUTED).pack(anchor='w',pady=(0,16))
    frame=tk.Frame(parent,bg='#1C2A24',padx=18,pady=18);frame.pack(fill='both',expand=True)
    scroll=ttk.Scrollbar(frame);scroll.pack(side='right',fill='y')
    app.log=tk.Text(frame,bg='#1C2A24',fg='#CDDCCD',selectbackground=GREEN,font=('Consolas',10),
                    relief='flat',wrap='word',state='disabled',yscrollcommand=scroll.set)
    app.log.pack(fill='both',expand=True);scroll.configure(command=app.log.yview)


def show(app, key):
    for name,page in app.pages.items():
        page.pack_forget()
        app.nav[name].configure(bg='#314B3E' if name==key else SIDEBAR,fg='#DFEFCE' if name==key else '#ABBDB2')
    app.pages[key].pack(fill='both',expand=True)
    app.page_title.configure(text={'overview':'工作台','models':'模型管理','files':'文件与目录','logs':'运行记录'}[key])
    app.current_page=key


def update_status(app, values):
    for service in app.services:
        caption,color=badge_state(service,values.get(service['id'],False))
        app.rows[service['id']].configure(text=caption,fg=color)
    count=sum(bool(v) for v in values.values())
    suffix='示例配置 · 未探测真实服务' if app.demo else time.strftime('%H:%M:%S')+' 更新'
    app.hero_summary.configure(text=f'{count} / {len(app.services)} 个接口就绪   ·   {suffix}')


def update_busy(app):
    busy=app.starting or app.stopping
    for b in app.start_buttons: b.state(['disabled'] if busy else ['!disabled'])
    # Preserve the portable launcher's stop-during-start behavior.
    for b in app.stop_buttons: b.state(['disabled'] if app.stopping else ['!disabled'])
    if busy:
        app.progress.pack(side='bottom',fill='x');app.progress.start(12)
        app.activity.configure(text='正在关闭已管理服务…' if app.stopping else '正在发出启动命令；仍可点击关闭取消剩余启动。')
    else:
        app.progress.stop();app.progress.pack_forget()


def button(app, parent, caption, callback, kind='Soft', lock=False):
    b = ttk.Button(parent, text=caption, command=callback, style=kind+'.TButton', cursor='hand2')
    if lock: app.buttons.append(b)
    return b
