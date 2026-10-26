"""Portable, validated workspace snapshots. No shell commands or process arguments."""
from copy import deepcopy
import json
import math
import ntpath
import time
import uuid
from urllib.parse import urlsplit

MAX_WINDOWS = 256
MAX_TABS = 200
BROWSERS = {'chrome.exe','msedge.exe','brave.exe','vivaldi.exe','opera.exe','firefox.exe'}
BLOCKED_LAUNCHERS = {'cmd.exe','powershell.exe','pwsh.exe','rundll32.exe','regsvr32.exe','mshta.exe','wscript.exe','cscript.exe','conhost.exe','python.exe','pythonw.exe','py.exe','java.exe','javaw.exe','msiexec.exe','setup.exe','reg.exe','shutdown.exe','taskkill.exe'}


def text(value, maximum, label):
    if not isinstance(value,str) or len(value)>maximum or '\x00' in value:
        raise ValueError('Invalid '+label)
    return value


def http_url(value):
    text(value,4096,'URL')
    try:
        parsed=urlsplit(value)
        return parsed.scheme.lower() in ('https','http') and bool(parsed.hostname) and not any(c in value for c in '\r\n')
    except ValueError:
        return False


def rectangle(value):
    if not isinstance(value,list) or len(value)!=4 or any(type(n) is not int or not -100000<=n<=100000 for n in value):
        raise ValueError('Invalid window rectangle')
    left,top,right,bottom=value
    if not 1<=right-left<=32768 or not 1<=bottom-top<=32768:
        raise ValueError('Invalid window size')
    return value


def validate_snapshot(snapshot):
    if not isinstance(snapshot,dict) or snapshot.get('version')!=1:
        raise ValueError('Invalid workspace version')
    for key,maximum in [('id',100),('name',160),('note',4000),('machine',256)]:
        text(snapshot.get(key),maximum,key)
    if not snapshot['id'] or not snapshot['name'].strip():raise ValueError('Workspace name required')
    if type(snapshot.get('created')) not in (int,float) or not math.isfinite(snapshot['created']) or not 0<=snapshot['created']<=253402300799:
        raise ValueError('Invalid workspace time')
    windows=snapshot.get('windows')
    if not isinstance(windows,list) or len(windows)>MAX_WINDOWS:raise ValueError('Too many windows')
    ids=set()
    for window in windows:
        if not isinstance(window,dict):raise ValueError('Invalid window')
        for key,maximum in [('id',100),('title',512),('exe',32760),('app',160),('target',4096),('position',160)]:
            text(window.get(key),maximum,key)
        if not window['id'] or window['id'] in ids:raise ValueError('Duplicate window ID')
        ids.add(window['id'])
        if window.get('kind') not in ('app','folder','document','browser'):raise ValueError('Invalid window kind')
        if window.get('show') not in (1,2,3):raise ValueError('Invalid window state')
        rectangle(window.get('rect'))
        for key in ('hwnd','pid','started'):
            if type(window.get(key)) is not int or not 0<=window[key]<2**64:raise ValueError('Invalid process identity')
        if type(window.get('unsaved')) is not bool:raise ValueError('Invalid unsaved flag')
        tabs=window.get('tabs',[])
        if not isinstance(tabs,list) or len(tabs)>MAX_TABS:raise ValueError('Too many tabs')
        for tab in tabs:
            if not isinstance(tab,dict) or not http_url(tab.get('url','')):raise ValueError('Unsupported browser URL')
            text(tab.get('title',''),512,'tab title')
            if type(tab.get('active',False)) is not bool or type(tab.get('pinned',False)) is not bool:raise ValueError('Invalid tab state')
    warnings=snapshot.get('warnings',[])
    if not isinstance(warnings,list) or len(warnings)>256:raise ValueError('Invalid warnings')
    for warning in warnings:text(warning,1000,'warning')
    return snapshot


def new_snapshot(name, windows, machine='', note='', warnings=None):
    return validate_snapshot(dict(version=1,id=str(uuid.uuid4()),name=name.strip(),note=note,created=time.time(),machine=machine,windows=windows,warnings=warnings or []))


class SessionStore:
    def __init__(self,db):
        self.db=db
        self.db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, name TEXT NOT NULL, created REAL NOT NULL, payload TEXT NOT NULL)')
        self.db.commit()

    def save(self,snapshot):
        validate_snapshot(snapshot)
        if not self.get(snapshot['id']) and self.db.execute('SELECT count(*) FROM sessions').fetchone()[0]>=200:
            raise ValueError('Maximum 200 workspaces. Delete an old workspace first.')
        encoded=json.dumps(snapshot,ensure_ascii=False)
        if len(encoded.encode('utf-8'))>8_000_000:raise ValueError('Workspace too large')
        with self.db:self.db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)',(snapshot['id'],snapshot['name'],snapshot['created'],encoded))
        return snapshot

    def all(self):
        return [json.loads(row[0]) for row in self.db.execute('SELECT payload FROM sessions ORDER BY created DESC')]

    def get(self,session_id):
        row=self.db.execute('SELECT payload FROM sessions WHERE id=?',(session_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self,session_id):
        with self.db:self.db.execute('DELETE FROM sessions WHERE id=?',(session_id,))


def imported_snapshot(snapshot):
    result=deepcopy(validate_snapshot(snapshot))
    # Imported files cannot claim native HWND/PID identity on the current computer.
    for window in result['windows']:
        window.update(hwnd=0,pid=0,started=0)
    return result


def launch_plan(window):
    """Only structured targets and an executable path. Never replay captured command lines."""
    executable=window['exe']
    basename=ntpath.basename(executable).lower()
    if window['kind']=='folder' and window['target']:
        return {'action':'folder','target':window['target']}
    if window['kind']=='document' and window['target']:
        return {'action':'document','target':window['target']}
    if not executable or not ntpath.isabs(executable) or basename in BLOCKED_LAUNCHERS or not basename.endswith('.exe') or '\\windowsapps\\' in executable.lower() or basename=='applicationframehost.exe':
        return {'action':'manual','reason':'Application needs manual reopening'}
    if window['kind']=='browser' and basename in BROWSERS:
        urls=[tab['url'] for tab in window.get('tabs',[]) if http_url(tab.get('url',''))]
        if not urls and http_url(window['target']):urls=[window['target']]
        if sum(len(url)+3 for url in urls)>26000:return {'action':'manual','reason':'Too many URL characters for Windows command line; use browser companion'}
        if basename=='firefox.exe':
            arguments=[]
            for index,url in enumerate(urls):arguments.extend(['-new-window' if index==0 else '-new-tab',url])
            return {'action':'launch','argv':[executable]+arguments,'coverage':'tabs' if urls else 'application'}
        return {'action':'launch','argv':[executable,'--new-window']+urls,'coverage':'tabs' if urls else 'application'}
    return {'action':'launch','argv':[executable],'coverage':'application'}


def clamp_rectangle(rect, workareas):
    rectangle(rect)
    if not workareas:return rect[:]
    left,top,right,bottom=rect
    def overlap(area):return max(0,min(right,area[2])-max(left,area[0]))*max(0,min(bottom,area[3])-max(top,area[1]))
    area=max(workareas,key=overlap)
    x,y,r,b=area
    width=min(right-left,r-x);height=min(bottom-top,b-y)
    new_left=max(x,min(left,r-width));new_top=max(y,min(top,b-height))
    return [new_left,new_top,new_left+width,new_top+height]


def merge_browser_export(snapshot, exported):
    result=deepcopy(validate_snapshot(snapshot))
    if not isinstance(exported,dict) or exported.get('format')!='backhere-browser' or exported.get('version')!=1:raise ValueError('Not a BackHere browser export')
    browser=exported.get('browser')
    if browser not in BROWSERS:raise ValueError('Unsupported browser')
    candidates=[w for w in result['windows'] if ntpath.basename(w['exe']).lower()==browser]
    if not candidates:raise ValueError('Capture this browser in the workspace before importing its tabs')
    windows=exported.get('windows')
    if not isinstance(windows,list) or len(windows)>64:raise ValueError('Invalid browser windows')
    replacements=[]
    for index,source in enumerate(windows):
        if not isinstance(source,dict) or source.get('incognito'):continue
        tabs=source.get('tabs')
        if not isinstance(tabs,list) or len(tabs)>MAX_TABS:raise ValueError('Too many tabs')
        cleaned=[]
        for tab in tabs:
            if not isinstance(tab,dict) or not http_url(tab.get('url','')):raise ValueError('Only HTTP/HTTPS tabs can be restored')
            cleaned.append(dict(url=tab['url'],title=text(tab.get('title',''),512,'tab title'),active=tab.get('active') is True,pinned=tab.get('pinned') is True))
        if not cleaned:continue
        base=deepcopy(candidates[min(index,len(candidates)-1)])
        if index>=len(candidates):base.update(id=str(uuid.uuid4()),hwnd=0,pid=0,started=0)
        base.update(kind='browser',tabs=cleaned,target=next((t['url'] for t in cleaned if t['active']),cleaned[0]['url']))
        replacements.append(base)
    if not replacements:raise ValueError('No restorable browser tabs')
    old_ids={w['id'] for w in candidates}
    result['windows']=[w for w in result['windows'] if w['id'] not in old_ids]+replacements
    return validate_snapshot(result)
