"""Windows notification icon, owned and pumped by the Tk UI thread."""
import ctypes as c
from ctypes import wintypes as w

LRESULT = c.c_ssize_t
WNDPROC = c.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class WNDCLASS(c.Structure):
    _fields_ = [('style', w.UINT), ('proc', WNDPROC), ('cls_extra', c.c_int),
                ('wnd_extra', c.c_int), ('instance', w.HINSTANCE), ('icon', w.HICON),
                ('cursor', w.HANDLE), ('background', w.HBRUSH),
                ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]


class NOTIFYICONDATA(c.Structure):
    _fields_ = [('size', w.DWORD), ('hwnd', w.HWND), ('id', w.UINT),
                ('flags', w.UINT), ('callback', w.UINT), ('icon', w.HICON),
                ('tip', w.WCHAR * 128), ('state', w.DWORD), ('mask', w.DWORD),
                ('info', w.WCHAR * 256), ('version', w.UINT),
                ('title', w.WCHAR * 64), ('info_flags', w.DWORD),
                ('guid', c.c_byte * 16), ('balloon_icon', w.HICON)]


class Tray:
    def __init__(self, restore, exit_app):
        self.restore, self.exit_app = restore, exit_app
        self.user = c.WinDLL('user32', use_last_error=True)
        self.shell = c.WinDLL('shell32', use_last_error=True)
        specs = {
            'DefWindowProcW': ([w.HWND, w.UINT, w.WPARAM, w.LPARAM], LRESULT),
            'RegisterClassW': ([c.POINTER(WNDCLASS)], w.ATOM),
            'CreateWindowExW': ([w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD,c.c_int,c.c_int,c.c_int,c.c_int,w.HWND,w.HMENU,w.HINSTANCE,c.c_void_p], w.HWND),
            'DestroyWindow': ([w.HWND], w.BOOL),
            'UnregisterClassW': ([w.LPCWSTR,w.HINSTANCE], w.BOOL),
            'LoadIconW': ([w.HINSTANCE,c.c_void_p], w.HICON),
            'RegisterWindowMessageW': ([w.LPCWSTR], w.UINT),
            'CreatePopupMenu': ([],w.HMENU),
            'AppendMenuW': ([w.HMENU,w.UINT,c.c_size_t,w.LPCWSTR],w.BOOL),
            'GetCursorPos': ([c.POINTER(w.POINT)],w.BOOL),
            'SetForegroundWindow': ([w.HWND],w.BOOL),
            'PostMessageW': ([w.HWND,w.UINT,w.WPARAM,w.LPARAM],w.BOOL),
            'TrackPopupMenu': ([w.HMENU,w.UINT,c.c_int,c.c_int,c.c_int,w.HWND,c.c_void_p],w.UINT),
            'DestroyMenu': ([w.HMENU],w.BOOL),
        }
        for name, (args, result) in specs.items():
            fn = getattr(self.user, name)
            fn.argtypes, fn.restype = args, result
        self.shell.Shell_NotifyIconW.argtypes = [w.DWORD,c.POINTER(NOTIFYICONDATA)]
        self.shell.Shell_NotifyIconW.restype = w.BOOL
        self.restart = self.user.RegisterWindowMessageW('TaskbarCreated')
        self.callback = WNDPROC(self.dispatch)
        self.name = 'ZhiyeTray' + str(id(self))
        self.cls = WNDCLASS(proc=self.callback, name=self.name)
        if not self.user.RegisterClassW(c.byref(self.cls)):
            raise c.WinError(c.get_last_error())
        self.hwnd = self.user.CreateWindowExW(0,self.name,self.name,0,0,0,0,0,None,None,None,None)
        if not self.hwnd:
            self.user.UnregisterClassW(self.name,None)
            raise c.WinError(c.get_last_error())
        self.data = NOTIFYICONDATA(size=c.sizeof(NOTIFYICONDATA),hwnd=self.hwnd,id=1,
            flags=7,callback=0x8001,icon=self.user.LoadIconW(None,32512),
            tip='知页工作台 · 单击恢复 / 右键菜单')
        if not self.shell.Shell_NotifyIconW(0,c.byref(self.data)):
            self.close()
            raise RuntimeError('Windows 无法创建托盘图标')

    def dispatch(self, hwnd, msg, wp, lp):
        if msg == self.restart and hasattr(self, 'data'):
            try:
                self.ensure_visible()
            except RuntimeError:
                self.restore()
            return 0
        if msg == 0x8001:
            if lp == 0x202: self.restore()
            elif lp == 0x205:
                menu = self.user.CreatePopupMenu()
                try:
                    self.user.AppendMenuW(menu,0,1,'打开工作台')
                    self.user.AppendMenuW(menu,0,2,'退出工作台（模型继续运行）')
                    point = w.POINT()
                    self.user.GetCursorPos(c.byref(point))
                    self.user.SetForegroundWindow(hwnd)
                    choice = self.user.TrackPopupMenu(menu,0x100 | 2,point.x,point.y,0,hwnd,None)
                    # Required for notification menus to reopen reliably, even
                    # after cancellation. Queue this before any exit callback.
                    self.user.PostMessageW(hwnd,0,0,0)  # WM_NULL
                    if choice == 1: self.restore()
                    elif choice == 2: self.exit_app()
                finally:
                    self.user.DestroyMenu(menu)
            return 0
        return self.user.DefWindowProcW(hwnd,msg,wp,lp)

    def ensure_visible(self):
        # Explorer can lose the icon while this Python object remains alive.
        # Never withdraw the workbench unless the shell accepts the icon.
        if not self.shell.Shell_NotifyIconW(1,c.byref(self.data)):
            if not self.shell.Shell_NotifyIconW(0,c.byref(self.data)):
                raise RuntimeError('Windows 无法恢复托盘图标；工作台保持可见')

    def close(self):
        if hasattr(self,'data'): self.shell.Shell_NotifyIconW(2,c.byref(self.data))
        if self.hwnd:
            self.user.DestroyWindow(self.hwnd)
            self.hwnd = None
            self.user.UnregisterClassW(self.name,None)
