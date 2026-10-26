"""Offline device-bound signed licenses and a 72-hour trial; no network access.

Local trial protection is a deterrent, not protection against an administrator
patching an open-source binary, deleting every anchor or reverting the whole OS.
"""
import base64
import ctypes
from ctypes import wintypes
import getpass
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import platform
import re
import time
import uuid
from license_public import PUBLIC_N,PUBLIC_E

TRIAL_SECONDS=72*60*60
REGISTRY_PATH=r'Software\RainyStudio\BackHere\Licensing'

def b64(data):return base64.urlsafe_b64encode(data).decode('ascii').rstrip('=')
def unb64(text):
    if not isinstance(text,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',text):raise ValueError('Invalid license encoding')
    return base64.urlsafe_b64decode(text+'='*((-len(text))%4))

def verify_license(token,device,n=PUBLIC_N,e=PUBLIC_E):
    if not isinstance(token,str) or len(token)>6000:raise ValueError('Invalid license key')
    parts=token.strip().split('.')
    if len(parts)!=3 or parts[0]!='BH1':raise ValueError('Invalid license format')
    raw=unb64(parts[1]);signature=unb64(parts[2]);size=(n.bit_length()+7)//8
    if len(signature)!=size or int.from_bytes(signature,'big')>=n:raise ValueError('Invalid signature')
    digest=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(raw).digest()
    expected=b'\x00\x01'+b'\xff'*(size-len(digest)-3)+b'\x00'+digest
    actual=pow(int.from_bytes(signature,'big'),e,n).to_bytes(size,'big')
    if not hmac.compare_digest(actual,expected):raise ValueError('Invalid license signature')
    data=json.loads(raw)
    if not isinstance(data,dict) or data.get('product')!='BackHere' or data.get('version')!=1 or data.get('plan')!='lifetime' or data.get('device')!=device:
        raise ValueError('License is not valid for this device')
    if not isinstance(data.get('customer'),str) or not 1<=len(data['customer'])<=160:raise ValueError('Invalid customer')
    if not isinstance(data.get('id'),str) or len(data['id'])>100:raise ValueError('Invalid license ID')
    return data


def device_id():
    if os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            machine=winreg.QueryValueEx(key,'MachineGuid')[0]
    else:machine=str(uuid.getnode())+'|'+platform.node()
    identity='BackHere-v1|'+machine+'|'+getpass.getuser().casefold()
    return 'BH-'+hashlib.sha256(identity.encode('utf-8')).hexdigest()[:32].upper()


class DATA_BLOB(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]

def protect(data,decrypt=False):
    if os.name!='nt':raise OSError('Windows DPAPI required')
    crypt=ctypes.windll.crypt32;kernel=ctypes.windll.kernel32
    buffer=ctypes.create_string_buffer(data);source=DATA_BLOB(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));output=DATA_BLOB()
    pointer=ctypes.POINTER(DATA_BLOB)
    if decrypt:
        fn=crypt.CryptUnprotectData;fn.argtypes=[pointer,ctypes.c_void_p,pointer,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,pointer]
    else:
        fn=crypt.CryptProtectData;fn.argtypes=[pointer,wintypes.LPCWSTR,pointer,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,pointer]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):raise ctypes.WinError()
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    try:return ctypes.string_at(output.pbData,output.cbData)
    finally:kernel.LocalFree(output.pbData)


class WindowsAnchors:
    """Independent registry/profile anchors survive normal uninstall/DB restore."""
    def __init__(self,folder):self.path=Path(folder)/'license-state.dat'
    def read(self):
        import winreg
        values=[]
        if self.path.exists():
            if self.path.stat().st_size>30000:raise ValueError('Invalid trial state')
            values.append(self.path.read_bytes())
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,REGISTRY_PATH) as key:
                data,kind=winreg.QueryValueEx(key,'State')
                if kind!=winreg.REG_BINARY or len(data)>30000:raise ValueError('Invalid trial state')
                values.append(data)
        except FileNotFoundError:pass
        return [json.loads(protect(value,decrypt=True)) for value in values]
    def write(self,state):
        import winreg
        raw=protect(json.dumps(state,separators=(',',':')).encode('utf-8'))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp');temporary.write_bytes(raw);temporary.replace(self.path)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,REGISTRY_PATH) as key:winreg.SetValueEx(key,'State',0,winreg.REG_BINARY,raw)


class MemoryAnchors:
    """Explicit test backend; never chosen by the production App."""
    def __init__(self):self.values=[]
    def read(self):return json.loads(json.dumps(self.values))
    def write(self,state):self.values=[json.loads(json.dumps(state))]


class LicenseManager:
    def __init__(self,backend,device,clock=time.time,verifier=verify_license):
        self.backend=backend;self.device=device;self.clock=clock;self.verifier=verifier;self.state=None;self.error=False
        try:
            now=self.clock();states=backend.read()
            for value in states:self.validate_state(value)
            self.state=dict(version=1,device=device,start=min((v['start'] for v in states),default=now),seen=max([now]+[v['seen'] for v in states]),token='')
            for value in states:
                if value.get('token'):
                    try:self.verifier(value['token'],device);self.state['token']=value['token'];break
                    except ValueError:pass
            backend.write(self.state)
        except (OSError,ValueError,TypeError,KeyError):self.error=True
    def validate_state(self,state):
        if not isinstance(state,dict) or state.get('version')!=1 or state.get('device')!=self.device:raise ValueError('Invalid trial state')
        for key in ('start','seen'):
            if type(state.get(key)) not in (int,float) or not math.isfinite(state[key]) or not 0<=state[key]<=253402300799:raise ValueError('Invalid trial time')
        if state['seen']<state['start']:raise ValueError('Invalid trial time')
        if not isinstance(state.get('token',''),str):raise ValueError('Invalid stored license')
    def status(self,persist=True):
        if self.state and self.state.get('token'):
            try:return dict(kind='licensed',remaining=0,customer=self.verifier(self.state['token'],self.device)['customer'])
            except ValueError:pass
        if self.error or self.state is None:return dict(kind='licenseError',remaining=0)
        now=self.clock()
        if now+300<self.state['seen']:return dict(kind='clockError',remaining=0)
        effective=max(now,self.state['seen']);self.state['seen']=effective
        if persist:
            try:self.backend.write(self.state)
            except OSError:self.error=True;return dict(kind='licenseError',remaining=0)
        remaining=max(0,int(self.state['start']+TRIAL_SECONDS-effective))
        return dict(kind='trial' if remaining else 'trialExpired',remaining=remaining)
    def allowed(self):return self.status()['kind'] in ('trial','licensed')
    def activate(self,token):
        data=self.verifier(token.strip(),self.device)
        now=self.clock()
        state=dict(self.state) if self.state else dict(version=1,device=self.device,start=now,seen=now,token='')
        state['token']=token.strip();self.backend.write(state);self.state=state;self.error=False
        return data
