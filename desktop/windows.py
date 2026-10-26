"""Windows integration: registered global hotkey, Explorer selection, foreground title.
No keylogger, clipboard scraping, admin access or persistent background service.
"""
import ctypes
from ctypes import wintypes
import json
import os
import queue
import subprocess
import threading


def foreground():
    if os.name != 'nt':
        return {'title': '', 'target': ''}
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    handle = user.GetForegroundWindow()
    length = user.GetWindowTextLengthW(handle)
    text = ctypes.create_unicode_buffer(length + 1)
    user.GetWindowTextW(handle, text, length + 1)
    return {'title': text.value[:160], 'target': '', 'hwnd': int(handle or 0)}


def explorer_selection(handle):
    """Resolve Explorer selected file via Shell COM; never infer a document path."""
    if os.name != 'nt' or not handle:
        return ''
    # The only interpolated value is an integer HWND obtained from user32.
    script = "$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $s=New-Object -ComObject Shell.Application; $w=@($s.Windows()) | Where-Object {$_.HWND -eq " + str(int(handle)) + "} | Select-Object -First 1; if($w){$i=@($w.Document.SelectedItems()); if($i.Count -gt 0){$i[0].Path | ConvertTo-Json -Compress}}"
    try:
        result = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, timeout=3, creationflags=0x08000000)
        value = json.loads(result.stdout.decode('utf-8-sig').strip()) if result.returncode == 0 and result.stdout.strip() else ''
        return value if isinstance(value, str) else ''
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ''


class Hotkey:
    def __init__(self, events):
        self.events = events
        self.thread_id = None
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        if os.name != 'nt':
            self.events.put(('hotkey_error', 'Windows only'))
            return
        user = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        # Ctrl+Alt+B, MOD_NOREPEAT. RegisterHotKey receives no other keystrokes.
        if not user.RegisterHotKey(None, 1, 0x0002 | 0x0001 | 0x4000, ord('B')):
            self.events.put(('hotkey_error', 'Ctrl+Alt+B is already in use'))
            return
        self.events.put(('hotkey_ready', ''))
        message = wintypes.MSG()
        try:
            while user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312:
                    source = foreground()
                    self.events.put(('capture', source))
        finally:
            user.UnregisterHotKey(None, 1)

    def stop(self):
        if self.thread_id and os.name == 'nt':
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
