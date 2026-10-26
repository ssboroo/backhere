"""Pointer-size safe Windows integrations shared by x86 and x64 builds."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading


def parse_hotkey(text):
    parts = text.upper().replace(' ', '').split('+')
    modifiers = {'CTRL': 2, 'ALT': 1, 'SHIFT': 4}
    if len(parts) < 2 or len(set(parts)) != len(parts):
        raise ValueError('Use Ctrl+Alt+B, Ctrl+Shift+B, or Alt+Shift+B')
    if any(p not in modifiers for p in parts[:-1]) or len(parts[-1]) != 1 or not parts[-1].isascii() or not parts[-1].isalnum():
        raise ValueError('Use Ctrl/Alt/Shift plus A-Z or 0-9')
    if not any(p in parts[:-1] for p in ('CTRL', 'ALT')):
        raise ValueError('Include Ctrl or Alt')
    return sum(modifiers[p] for p in parts[:-1]) | 0x4000, ord(parts[-1])


def foreground():
    if os.name != 'nt':
        return {'title': '', 'target': '', 'position': ''}
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    handle = user.GetForegroundWindow()
    text = ctypes.create_unicode_buffer(min(user.GetWindowTextLengthW(handle), 4096) + 1)
    user.GetWindowTextW(handle, text, len(text))
    process_id = wintypes.DWORD()
    user.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
    return {'title': text.value[:160], 'target': '', 'position': '', 'hwnd': int(handle or 0), 'pid': process_id.value}


# No interpolated user text; only numeric HWND/process IDs obtained from user32.
CAPTURE_SCRIPT = r'''
$ErrorActionPreference='Stop'
$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$target=''; $position=''
$name=(Get-Process -Id PROCESS_ID -ErrorAction SilentlyContinue).ProcessName
if($name -eq 'explorer') {
 $s=New-Object -ComObject Shell.Application
 $w=@($s.Windows()) | Where-Object {$_.HWND -eq WINDOW_ID} | Select-Object -First 1
 if($w) { $i=@($w.Document.SelectedItems()); if($i.Count -gt 0){$target=$i[0].Path} }
} elseif($name -in @('chrome','msedge','firefox','brave','vivaldi','opera')) {
 Add-Type -AssemblyName UIAutomationClient
 $window=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]WINDOW_ID)
 $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)
 $edits=$window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
 foreach($edit in $edits) {
  $r=$edit.Current.BoundingRectangle
  if($r.Top -lt $window.Current.BoundingRectangle.Top -or $r.Top -gt ($window.Current.BoundingRectangle.Top+160) -or $edit.Current.IsOffscreen){continue}
  if($edit.Current.AutomationId -notin @('addressEditBox','urlbar-input') -and $edit.Current.Name -notmatch '(?i)address|location|adresse|direcci[oó]n|endere[cç]o|адрес|хаяг|地址|アドレス|주소|عنوان|adres'){continue}
  $pattern=$null
  if($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)) {
   $value=$pattern.Current.Value
   if($value -match '^https?://[^/\s]+') {$target=$value; break}
   if($edit.Current.AutomationId -eq 'addressEditBox' -and $value -match '^[\w-]+(\.[\w-]+)+([/:?#].*)?$') {$target='https://'+$value; break}
  }
 }
} elseif($name -eq 'WINWORD') {
 $word=[Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')
 if($word.ActiveWindow.Hwnd -eq WINDOW_ID -and $word.ActiveDocument.Path) {
  $target=$word.ActiveDocument.FullName
  $position='Page '+$word.Selection.Information(3)
 }
} elseif($name -eq 'EXCEL') {
 $excel=[Runtime.InteropServices.Marshal]::GetActiveObject('Excel.Application')
 if(($excel.Hwnd -eq WINDOW_ID -or $excel.ActiveWindow.Hwnd -eq WINDOW_ID) -and $excel.ActiveWorkbook.Path) {
  $target=$excel.ActiveWorkbook.FullName
  $position=$excel.ActiveSheet.Name+'!'+$excel.ActiveCell.Address($false,$false)
 }
}
@{target=$target;position=$position} | ConvertTo-Json -Compress
'''


def capture_target(source):
    if os.name != 'nt' or not source.get('hwnd'):
        return {'target': '', 'position': ''}
    script = CAPTURE_SCRIPT.replace('WINDOW_ID', str(int(source['hwnd']))).replace('PROCESS_ID', str(int(source.get('pid', 0))))
    try:
        result = subprocess.run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, timeout=4, creationflags=0x08000000)
        data = json.loads(result.stdout.decode('utf-8-sig').strip()) if result.returncode == 0 and result.stdout.strip() else {}
        return {k: data.get(k, '')[:2048 if k == 'target' else 160] if isinstance(data.get(k), str) else '' for k in ('target', 'position')}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {'target': '', 'position': ''}


class Hotkey:
    REBIND = 0x8001

    def __init__(self, events, shortcut='Ctrl+Alt+B'):
        parse_hotkey(shortcut)
        self.events, self.shortcut = events, shortcut
        self.thread_id = None
        self.commands = queue.Queue()
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def rebind(self, shortcut):
        parse_hotkey(shortcut)
        if not self.ready.is_set() or os.name != 'nt':
            return False
        self.commands.put(shortcut)
        return bool(ctypes.windll.user32.PostThreadMessageW(self.thread_id, self.REBIND, 0, 0))

    def run(self):
        if os.name != 'nt':
            self.events.put(('hotkey_error', self.shortcut))
            return
        user = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        message = wintypes.MSG()
        user.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)  # create message queue
        registered = False
        active_id = 1
        modifiers, key = parse_hotkey(self.shortcut)
        registered = bool(user.RegisterHotKey(None, 1, modifiers, key))
        self.events.put(('hotkey_ready' if registered else 'hotkey_error', self.shortcut))
        self.ready.set()
        try:
            while not self.stopping.is_set() and user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == 0x0312:
                    self.events.put(('capture', foreground()))
                elif message.message == self.REBIND:
                    requested = self.commands.get_nowait()
                    if requested == self.shortcut and registered:
                        self.events.put(('hotkey_ready', requested))
                        continue
                    # Keep the old registration until a replacement has succeeded.
                    modifiers, key = parse_hotkey(requested)
                    replacement_id = 2 if active_id == 1 else 1
                    if user.RegisterHotKey(None, replacement_id, modifiers, key):
                        if registered:
                            user.UnregisterHotKey(None, active_id)
                        active_id = replacement_id
                        registered = True
                        self.shortcut = requested
                        self.events.put(('hotkey_ready', requested))
                    else:
                        self.events.put(('hotkey_error', requested))
        finally:
            user.UnregisterHotKey(None, active_id)

    def stop(self):
        self.stopping.set()
        if self.thread_id and os.name == 'nt':
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
        if threading.current_thread() is not self.thread:
            self.thread.join(timeout=1)


class SingleInstance:
    def __init__(self):
        self.handle = None
        self.already_running = False
        if os.name == 'nt':
            kernel = ctypes.windll.kernel32
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            self.handle = kernel.CreateMutexW(None, False, 'Local\\BackHere.Desktop.v1')
            if not self.handle:
                raise ctypes.WinError()
            self.already_running = kernel.GetLastError() == 183

    def close(self):
        if self.handle:
            ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None


def signal_existing():
    """Named per-session event also restores a hidden/tray window."""
    kernel = ctypes.windll.kernel32
    kernel.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenEventW.restype = wintypes.HANDLE
    event = kernel.OpenEventW(2, False, 'Local\\BackHere.Show.v1')
    if event:
        kernel.SetEvent.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.SetEvent(event)
        kernel.CloseHandle(event)


class ShowSignal:
    def __init__(self):
        self.handle = None
        if os.name == 'nt':
            kernel = ctypes.windll.kernel32
            kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
            kernel.CreateEventW.restype = wintypes.HANDLE
            self.handle = kernel.CreateEventW(None, False, False, 'Local\\BackHere.Show.v1')
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]

    def pending(self):
        return bool(self.handle and ctypes.windll.kernel32.WaitForSingleObject(self.handle, 0) == 0)

    def close(self):
        if self.handle:
            ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None


def set_startup(enabled):
    if os.name != 'nt':
        raise OSError('Windows only')
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
        if enabled:
            executable = sys.executable
            arguments = [executable, '--background'] if getattr(sys, 'frozen', False) else [str(Path(executable).with_name('pythonw.exe')), str(Path(__file__).with_name('backhere.py')), '--background']
            winreg.SetValueEx(key, 'BackHere', 0, winreg.REG_SZ, subprocess.list2cmdline(arguments))
        else:
            try:
                winreg.DeleteValue(key, 'BackHere')
            except FileNotFoundError:
                pass


def startup_enabled():
    if os.name != 'nt':
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            return bool(winreg.QueryValueEx(key, 'BackHere')[0])
    except FileNotFoundError:
        return False
