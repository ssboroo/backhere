import os
import queue
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from windows import parse_hotkey, Hotkey, SingleInstance, ShowSignal, signal_existing, foreground


class ShortcutParserTests(unittest.TestCase):
    def test_valid_shortcuts(self):
        self.assertEqual(parse_hotkey('Ctrl+Alt+B'), (0x4003, ord('B')))
        self.assertEqual(parse_hotkey('Ctrl+Shift+7'), (0x4006, ord('7')))
        self.assertEqual(parse_hotkey('alt + shift + z'), (0x4005, ord('Z')))

    def test_invalid_shortcuts(self):
        for shortcut in ('B', 'Ctrl+Ctrl+B', 'Win+B', 'Shift+B', 'Ctrl+Alt+Б', 'Ctrl+Alt+F12', 'Ctrl++B'):
            with self.subTest(shortcut=shortcut), self.assertRaises(ValueError):
                parse_hotkey(shortcut)


@unittest.skipUnless(os.name == 'nt', 'Native Windows API tests')
class WindowsIntegrationTests(unittest.TestCase):
    def event(self, events, kind):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            event = events.get(timeout=4)
            if event[0] == kind:
                return event
        self.fail('Missing event ' + kind)

    def test_instance_mutex_and_show_event(self):
        first = SingleInstance()
        second = SingleInstance()
        signal = ShowSignal()
        try:
            self.assertFalse(first.already_running)
            self.assertTrue(second.already_running)
            self.assertFalse(signal.pending())
            signal_existing()
            self.assertTrue(signal.pending())
            self.assertFalse(signal.pending())
        finally:
            signal.close()
            second.close()
            first.close()

    def test_global_shortcut_rebind_collision_and_shutdown(self):
        import ctypes
        from ctypes import wintypes
        events = queue.Queue()
        hotkey = Hotkey(events, 'Ctrl+Alt+Shift+8')
        try:
            self.assertEqual(self.event(events, 'hotkey_ready')[1], 'Ctrl+Alt+Shift+8')
            self.assertTrue(hotkey.ready.wait(1))
            # Deliver the exact WM_HOTKEY notification Windows dispatches on keypress.
            ctypes.windll.user32.PostThreadMessageW(hotkey.thread_id, 0x0312, 1, 0)
            self.assertIsInstance(self.event(events, 'capture')[1]['title'], str)
            self.assertTrue(hotkey.rebind('Ctrl+Alt+Shift+9'))
            self.assertEqual(self.event(events, 'hotkey_ready')[1], 'Ctrl+Alt+Shift+9')
            # Another thread cannot register the same process-wide shortcut.
            conflict_events = queue.Queue()
            conflict = Hotkey(conflict_events, 'Ctrl+Alt+Shift+9')
            try:
                self.event(conflict_events, 'hotkey_error')
            finally:
                conflict.stop()
        finally:
            hotkey.stop()
        self.assertFalse(hotkey.thread.is_alive())

    def test_foreground_handle_is_pointer_safe(self):
        data = foreground()
        self.assertIsInstance(data['hwnd'], int)
        self.assertIsInstance(data['pid'], int)
        self.assertIsInstance(data['title'], str)
