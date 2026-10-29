"""Set ZHIYE_GUI_TESTS=1 on a desktop (or under Xvfb) to exercise real Tk widgets."""
import os
import gc
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, call, patch

from desktop_ui import badge_state


class BadgeTests(unittest.TestCase):
    def test_disabled_is_not_claimed_stopped(self):
        service={'enabled':False,'command':[]}
        self.assertIn('未启用',badge_state(service,False)[0])
        self.assertIn('接口就绪',badge_state(service,True)[0])

    def test_enabled_offline(self):
        self.assertIn('未就绪',badge_state({'enabled':True,'command':['python']},False)[0])


@unittest.skipUnless(os.name == 'nt', 'Windows native tray')
class TrayMenuTests(unittest.TestCase):
    def test_repeated_menus_post_null_after_selection_and_cancel(self):
        from tray import Tray
        tray = Tray.__new__(Tray)
        tray.restart = 0xC001
        tray.user = Mock()
        tray.user.CreatePopupMenu.return_value = 456
        tray.restore, tray.exit_app = Mock(), Mock()
        for choice in (0, 1, 2, 0):
            with self.subTest(choice=choice):
                tray.user.reset_mock()
                tray.user.TrackPopupMenu.return_value = choice
                tray.dispatch(123, 0x8001, 1, 0x205)
                tray.user.assert_has_calls([
                    call.SetForegroundWindow(123),
                    call.TrackPopupMenu(456,0x100 | 2,0,0,0,123,None),
                    call.PostMessageW(123,0,0,0),
                    call.DestroyMenu(456),
                ])
                tray.user.PostMessageW.assert_called_once_with(123,0,0,0)
        tray.restore.assert_called_once_with()
        tray.exit_app.assert_called_once_with()


@unittest.skipUnless(os.getenv('ZHIYE_GUI_TESTS')=='1','Set ZHIYE_GUI_TESTS=1 with a display')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        from launcher import Launcher
        self.folder=tempfile.TemporaryDirectory()
        self.services=[{'id':'knowledge','label':'知页知识库','group':'app','enabled':True,'command':['fixture'],
                        'open_url':'http://127.0.0.1:8090/'},
                       {'id':'embedding','label':'嵌入模型','group':'model','enabled':False,'command':[]}]
        self.manager=Mock()
        self.manager.healthy.return_value=False
        self.manager.start.return_value='fixture started'
        self.manager.stop.return_value='fixture stopped'
        self.app=Launcher(root=Path(self.folder.name),services=self.services,manager=self.manager,auto_refresh=False)
        self.app.update()

    def tearDown(self):
        self.settle(lambda:not self.app.checking and not self.app.starting and not self.app.stopping)
        self.app.close_window()
        self.app = None
        # Tk cycles must be collected here, not later by FastAPI's worker threads.
        gc.collect()
        self.folder.cleanup()

    def settle(self, predicate):
        deadline=time.monotonic()+3
        while not predicate() and time.monotonic()<deadline:
            self.app.update();time.sleep(.01)
        self.assertTrue(predicate())

    def test_navigation_minimum_layout_and_configured_rows(self):
        import desktop_ui as ui
        self.app.geometry('1120x780');self.app.update()
        self.assertEqual(set(self.app.rows),{'knowledge','embedding'})
        for key in ('models','files','logs','overview'):
            ui.show(self.app,key);self.app.update()
            self.assertTrue(self.app.pages[key].winfo_ismapped())
            self.assertEqual(self.app.current_page,key)
        for card in self.app.cards:
            self.assertGreater(card.winfo_width(),350)

    def test_stop_confirmation_cancel_has_no_effect(self):
        with patch('launcher.messagebox.askyesno',return_value=False):
            self.app.stop(self.services)
        self.manager.stop.assert_not_called()
        self.assertFalse(self.app.cancel.is_set())

    def test_stop_during_start_cancels_remaining_and_restores_buttons(self):
        entered,release=threading.Event(),threading.Event()
        def waiting(service,cancel):
            entered.set();release.wait(2)
            return 'start finished'
        self.manager.start.side_effect=waiting
        self.app.start(self.services)
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(all('disabled' not in b.state() for b in self.app.stop_buttons))
            with patch('launcher.messagebox.askyesno',return_value=True):
                self.app.stop(self.services)
            self.assertTrue(self.app.cancel.is_set())
        finally:
            release.set()
        self.settle(lambda:not self.app.starting and not self.app.stopping)
        self.assertEqual(self.manager.start.call_count,1)
        self.assertEqual(self.manager.stop.call_count,2)
        self.assertTrue(all('disabled' not in b.state() for b in self.app.start_buttons))

    def test_demo_cannot_mutate_or_probe(self):
        self.app.demo=True
        self.app.start(self.services);self.app.stop(self.services);self.app.refresh()
        with patch('launcher.webbrowser.open') as browser:
            self.app.open_service(self.services[0]);browser.assert_not_called()
        self.manager.start.assert_not_called();self.manager.stop.assert_not_called()
        self.manager.healthy.assert_not_called()

    def test_health_badges_and_failure_recovery(self):
        import desktop_ui as ui
        ui.update_status(self.app,{'knowledge':True})
        self.assertIn('接口就绪',self.app.rows['knowledge'].cget('text'))
        self.assertIn('未启用',self.app.rows['embedding'].cget('text'))
        self.manager.start.side_effect=RuntimeError('test failure')
        self.app.start(self.services[:1])
        self.settle(lambda:not self.app.starting)
        self.assertIn('test failure',self.app.log.get('1.0','end'))

    def test_closing_window_never_stops_services(self):
        # tearDown performs the actual close; no implicit calls should be scheduled.
        self.app.protocol('WM_DELETE_WINDOW')
        self.manager.stop.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows native tray')
    def test_native_tray_hide_restore_reuse_and_cleanup(self):
        self.app.hide_to_tray(); self.app.update()
        self.assertEqual(self.app.state(), 'withdrawn')
        tray = self.app.tray
        self.assertTrue(tray.hwnd)
        tray.dispatch(tray.hwnd, 0x8001, 1, 0x202)
        self.app.update()
        self.assertEqual(self.app.state(), 'normal')
        self.app.hide_to_tray(); self.app.update()
        self.assertIs(self.app.tray, tray)
        tray.close(); self.app.tray = None
        self.assertIsNone(tray.hwnd)
        self.manager.start.assert_not_called()
        self.manager.stop.assert_not_called()

    @unittest.skipUnless(os.name == 'nt', 'Windows native tray')
    def test_tray_failure_keeps_window_visible(self):
        with patch('tray.Tray', side_effect=RuntimeError('unavailable')), patch('launcher.messagebox.showwarning'):
            self.app.hide_to_tray(); self.app.update()
        self.assertEqual(self.app.state(), 'normal')

    def test_exit_is_blocked_during_start_or_stop(self):
        with patch.object(self.app, 'close_window') as close, patch('launcher.messagebox.showinfo'):
            self.app.starting = True
            self.app.request_exit(); close.assert_not_called()
            self.app.starting = False
            self.app.stopping = True
            self.app.request_exit(); close.assert_not_called()
            self.app.stopping = False
            self.app.request_exit(); close.assert_called_once()

    @unittest.skipUnless(os.name == 'nt', 'Windows native tray')
    def test_explorer_recovery_failure_cannot_hide_without_icon(self):
        self.app.hide_to_tray(); self.app.update()
        tray = self.app.tray
        with patch.object(tray.shell, 'Shell_NotifyIconW', return_value=False), patch('launcher.messagebox.showwarning'):
            tray.dispatch(tray.hwnd, tray.restart, 0, 0)
            self.app.update()
            self.assertEqual(self.app.state(), 'normal')
            self.app.hide_to_tray(); self.app.update()
            self.assertEqual(self.app.state(), 'normal')


if __name__=='__main__':unittest.main()
