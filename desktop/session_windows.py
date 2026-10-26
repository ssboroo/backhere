"""Windows desktop snapshots and best-effort restore, pointer-safe on x86 and x64."""
import ctypes
from ctypes import wintypes
import json
import ntpath
import os
from pathlib import Path
import platform
import subprocess
import time
import uuid
from session_model import BROWSERS, clamp_rectangle, launch_plan, new_snapshot, http_url
from core import open_target


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_=[('length',wintypes.UINT),('flags',wintypes.UINT),('showCmd',wintypes.UINT),('ptMinPosition',wintypes.POINT),('ptMaxPosition',wintypes.POINT),('rcNormalPosition',wintypes.RECT)]


class MONITORINFO(ctypes.Structure):
    _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',wintypes.RECT),('rcWork',wintypes.RECT),('dwFlags',wintypes.DWORD)]


def apis():
    if os.name!='nt':raise OSError('Windows desktop sessions require Windows')
    user=ctypes.windll.user32;kernel=ctypes.windll.kernel32
    user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user.GetClassNameW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
    user.IsWindowVisible.argtypes=[wintypes.HWND]
    user.GetWindow.argtypes=[wintypes.HWND,wintypes.UINT];user.GetWindow.restype=wintypes.HWND
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowPlacement.argtypes=[wintypes.HWND,ctypes.POINTER(WINDOWPLACEMENT)]
    user.SetWindowPlacement.argtypes=[wintypes.HWND,ctypes.POINTER(WINDOWPLACEMENT)]
    user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
    user.ShowWindow.argtypes=[wintypes.HWND,ctypes.c_int]
    user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    user.GetMonitorInfoW.argtypes=[wintypes.HANDLE,ctypes.POINTER(MONITORINFO)]
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    return user,kernel


def process_identity(pid,kernel):
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return '',0
    try:
        value=ctypes.create_unicode_buffer(32768);length=wintypes.DWORD(len(value))
        path=value.value if kernel.QueryFullProcessImageNameW(handle,0,value,ctypes.byref(length)) else ''
        times=[wintypes.FILETIME() for _ in range(4)]
        started=0
        if kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]):started=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
        return path,started
    finally:kernel.CloseHandle(handle)


def enumerate_windows(exclude_pid=None):
    user,kernel=apis();records=[];cache={}
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(hwnd,_):
        try:
            if not user.IsWindowVisible(hwnd) or user.GetWindow(hwnd,4):return True
            title=ctypes.create_unicode_buffer(513);user.GetWindowTextW(hwnd,title,len(title))
            if not title.value.strip():return True
            cls=ctypes.create_unicode_buffer(256);user.GetClassNameW(hwnd,cls,len(cls))
            if cls.value in ('Progman','WorkerW','Shell_TrayWnd','Shell_SecondaryTrayWnd','tooltips_class32'):return True
            try:
                cloaked=wintypes.DWORD()
                ctypes.windll.dwmapi.DwmGetWindowAttribute.argtypes=[wintypes.HWND,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD]
                if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd,14,ctypes.byref(cloaked),ctypes.sizeof(cloaked))==0 and cloaked.value:return True
            except OSError:pass
            pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==exclude_pid:return True
            if pid.value not in cache:cache[pid.value]=process_identity(pid.value,kernel)
            path,started=cache[pid.value]
            placement=WINDOWPLACEMENT();placement.length=ctypes.sizeof(placement)
            if not user.GetWindowPlacement(hwnd,ctypes.byref(placement)):return True
            # Screen coordinates for a visible normal window; workspace coordinates for
            # minimized/maximized windows are converted using its monitor's work offset.
            normal=placement.rcNormalPosition
            rect=[normal.left,normal.top,normal.right,normal.bottom]
            if placement.showCmd not in (2,3):
                actual=wintypes.RECT()
                if user.GetWindowRect(hwnd,ctypes.byref(actual)):rect=[actual.left,actual.top,actual.right,actual.bottom]
            else:
                user.MonitorFromWindow.argtypes=[wintypes.HWND,wintypes.DWORD];user.MonitorFromWindow.restype=wintypes.HANDLE
                info=MONITORINFO();info.cbSize=ctypes.sizeof(info)
                monitor=user.MonitorFromWindow(hwnd,2)
                if user.GetMonitorInfoW(monitor,ctypes.byref(info)):
                    dx=info.rcWork.left-info.rcMonitor.left;dy=info.rcWork.top-info.rcMonitor.top
                    rect=[rect[0]+dx,rect[1]+dy,rect[2]+dx,rect[3]+dy]
            if rect[2]<=rect[0] or rect[3]<=rect[1]:return True
            base=ntpath.basename(path).lower()
            records.append(dict(id=str(uuid.uuid4()),title=title.value,app=ntpath.basename(path) or cls.value,exe=path,hwnd=int(hwnd),pid=pid.value,started=started,rect=rect,show=placement.showCmd if placement.showCmd in (2,3) else 1,kind='browser' if base in BROWSERS else 'app',target='',position='',unsaved=False,tabs=[]))
        except (OSError,ValueError):pass
        return len(records)<256
    callback=callback_type(visit)
    user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    if not user.EnumWindows(callback,0) and len(records)<256:raise ctypes.WinError()
    return records


DETAIL_SCRIPT=r'''
$ErrorActionPreference='Stop';$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new()
$inputData=[Console]::In.ReadToEnd() | ConvertFrom-Json
$result=@{}
try { $shell=New-Object -ComObject Shell.Application; foreach($w in @($shell.Windows())) {
 $key=[string]$w.HWND; if($w.Document.Folder.Self.Path){$result[$key]=@{kind='folder';target=[string]$w.Document.Folder.Self.Path;position='';unsaved=$false}}
}} catch {}
try { $word=[Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application'); foreach($doc in @($word.Documents)){foreach($w in @($doc.Windows)){
 $result[[string]$w.Hwnd]=@{kind='document';target=$(if($doc.Path){[string]$doc.FullName}else{''});position='';unsaved=(!$doc.Saved)}
}}} catch {}
try { $excel=[Runtime.InteropServices.Marshal]::GetActiveObject('Excel.Application'); foreach($book in @($excel.Workbooks)){foreach($w in @($book.Windows)){
 $result[[string]$w.Hwnd]=@{kind='document';target=$(if($book.Path){[string]$book.FullName}else{''});position=[string]$book.ActiveSheet.Name;unsaved=(!$book.Saved)}
}}} catch {}
try { Add-Type -AssemblyName UIAutomationClient
 foreach($entry in @($inputData)){
  if($entry.app -notin @('chrome.exe','msedge.exe','firefox.exe','brave.exe','vivaldi.exe','opera.exe')){continue}
  try {
   $window=[System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]([long]$entry.hwnd))
   $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit)
   foreach($edit in $window.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)){
    if($edit.Current.IsOffscreen -or $edit.Current.BoundingRectangle.Top -gt ($window.Current.BoundingRectangle.Top+160)){continue}
    if($edit.Current.AutomationId -notin @('addressEditBox','urlbar-input') -and $edit.Current.Name -notmatch '(?i)address|location|adresse|direcci[oó]n|адрес|хаяг|地址|アドレス|주소|عنوان|adres'){continue}
    $pattern=$null
    if($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern) -and $pattern.Current.Value -match '^https?://'){
     $result[[string]$entry.hwnd]=@{kind='browser';target=[string]$pattern.Current.Value;position='';unsaved=$false};break
    }
   }
  }catch{}
 }
}catch{}
$result | ConvertTo-Json -Depth 5 -Compress
'''


def capture_workspace(name):
    records=enumerate_windows(os.getpid());warnings=[]
    try:
        system=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
        payload=json.dumps([{'hwnd':w['hwnd'],'app':ntpath.basename(w['exe']).lower()} for w in records])
        process=subprocess.run([str(system),'-NoLogo','-NoProfile','-NonInteractive','-Command',DETAIL_SCRIPT],input=payload.encode('utf-8'),capture_output=True,timeout=12,creationflags=0x08000000)
        details=json.loads(process.stdout.decode('utf-8-sig')) if process.returncode==0 and process.stdout.strip() else {}
        for record in records:
            detail=details.get(str(record['hwnd']),{})
            if detail.get('kind') in ('folder','document','browser'):
                record.update(kind=detail['kind'],target=str(detail.get('target',''))[:4096],position=str(detail.get('position',''))[:160],unsaved=detail.get('unsaved') is True)
                if record['kind']=='browser' and not http_url(record['target']):record['target']=''
    except (OSError,ValueError,subprocess.TimeoutExpired):warnings.append('Some document/URL details were unavailable; application windows were still saved.')
    return new_snapshot(name,records,platform.node(),warnings=warnings)


def workareas():
    user,_=apis();areas=[]
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HANDLE,wintypes.HDC,ctypes.POINTER(wintypes.RECT),wintypes.LPARAM)
    def visit(monitor,_dc,_rect,_data):
        info=MONITORINFO();info.cbSize=ctypes.sizeof(info)
        if user.GetMonitorInfoW(monitor,ctypes.byref(info)):
            r=info.rcWork;areas.append([r.left,r.top,r.right,r.bottom])
        return True
    callback=callback_type(visit)
    user.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.POINTER(wintypes.RECT),callback_type,wintypes.LPARAM]
    user.EnumDisplayMonitors(None,None,callback,0)
    return areas


def place_window(hwnd,rect,show):
    user,_=apis();left,top,right,bottom=clamp_rectangle(rect,workareas())
    user.ShowWindow(hwnd,9)
    # No activation or z-order takeover. Never move windows belonging to BackHere.
    if not user.SetWindowPos(hwnd,None,left,top,right-left,bottom-top,0x0004|0x0010):raise ctypes.WinError()
    if show==3:user.ShowWindow(hwnd,3)
    elif show==2:user.ShowWindow(hwnd,6)


def match_window(saved,current,used):
    candidates=[w for w in current if w['hwnd'] not in used and w['exe'].casefold()==saved['exe'].casefold()]
    identity=next((w for w in candidates if saved['started'] and (w['hwnd'],w['pid'],w['started'])==(saved['hwnd'],saved['pid'],saved['started'])),None)
    if identity:return identity
    return next((w for w in candidates if w['title']==saved['title']),None)


def restore_workspace(snapshot,selected_ids,cancel=None,progress=None):
    from session_model import validate_snapshot
    validate_snapshot(snapshot)
    results=[];used=set();launched_apps=set();current=enumerate_windows(os.getpid())
    for saved in snapshot['windows']:
        if saved['id'] not in selected_ids:continue
        if cancel and cancel.is_set():break
        report={'title':saved['title'],'state':'failed','detail':''}
        try:
            existing=match_window(saved,current,used)
            if existing:
                place_window(existing['hwnd'],saved['rect'],saved['show']);used.add(existing['hwnd'])
                report.update(state='reused',detail='Existing window repositioned; current document/tab state was left unchanged.')
            else:
                plan=launch_plan(saved)
                if plan['action']=='manual':report.update(state='manual',detail=plan['reason'])
                elif plan['action']=='launch' and plan['coverage']=='application' and saved['exe'].casefold() in launched_apps:
                    report.update(state='manual',detail='App already reopened; additional document/window needs manual recovery.')
                else:
                    before={w['hwnd'] for w in current}
                    if plan['action'] in ('folder','document'):
                        if not Path(plan['target']).exists():raise FileNotFoundError(plan['target'])
                        open_target(plan['target'])
                    else:
                        if not Path(saved['exe']).is_file():raise FileNotFoundError(saved['exe'])
                        subprocess.Popen(plan['argv'],shell=False,close_fds=True)
                        launched_apps.add(saved['exe'].casefold())
                    found=None
                    deadline=time.monotonic()+6
                    while time.monotonic()<deadline:
                        if cancel and cancel.is_set():break
                        time.sleep(.2)
                        current=enumerate_windows(os.getpid())
                        possible=[w for w in current if w['hwnd'] not in before and w['hwnd'] not in used and w['exe'].casefold()==saved['exe'].casefold()]
                        found=next((w for w in possible if w['title']==saved['title']),None) or (possible[0] if len(possible)==1 else None)
                        if found:break
                    if found:
                        place_window(found['hwnd'],saved['rect'],saved['show']);used.add(found['hwnd'])
                        report.update(state='opened',detail='Opened and positioned. Unsaved buffers, exact document state and browser form data are not restored.')
                    else:report.update(state='requested',detail='Open request sent; no uniquely matching new window was confirmed. Check the app manually.')
        except (OSError,ValueError) as exc:report['detail']=str(exc)
        results.append(report)
        if progress:progress(report)
    return results


def hibernate_windows():
    if os.name!='nt':raise OSError('Windows only')
    program=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/shutdown.exe'
    try:
        result=subprocess.run([str(program),'/h'],capture_output=True,timeout=15,creationflags=0x08000000)
    except subprocess.TimeoutExpired as exc:
        raise OSError('Windows did not confirm hibernation in time') from exc
    if result.returncode:raise OSError((result.stderr or result.stdout).decode(errors='replace').strip() or 'Windows hibernation is unavailable')
