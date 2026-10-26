import base64
from copy import deepcopy
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from licensing import LicenseManager,MemoryAnchors,TRIAL_SECONDS,b64,verify_license,protect,WindowsAnchors,device_id

FIXTURE=json.loads(Path(__file__).with_name('license-fixture.json').read_text())
N=int(FIXTURE['n']);D=int(FIXTURE['d']);VERIFY=partial(verify_license,n=N,e=FIXTURE['e'])
DEVICE='BH-'+'A'*32

def sign(device=DEVICE):
 raw=json.dumps(dict(version=1,product='BackHere',plan='lifetime',device=device,customer='Test customer',id='test-id'),sort_keys=True,separators=(',',':')).encode()
 digest=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(raw).digest();size=(N.bit_length()+7)//8
 em=b'\0\1'+b'\xff'*(size-len(digest)-3)+b'\0'+digest
 signature=pow(int.from_bytes(em,'big'),D,N).to_bytes(size,'big')
 return 'BH1.'+b64(raw)+'.'+b64(signature)

class LicenseTests(unittest.TestCase):
 def manager(self,backend=None,now=1000000):
  self.now=now;return LicenseManager(backend or MemoryAnchors(),DEVICE,lambda:self.now,VERIFY)
 def test_72_hours_exact_boundary_and_readonly_status(self):
  manager=self.manager();self.assertTrue(manager.allowed());self.assertEqual(manager.status()['remaining'],TRIAL_SECONDS)
  self.now+=TRIAL_SECONDS-1;self.assertTrue(manager.allowed());self.now+=1;self.assertFalse(manager.allowed());self.assertEqual(manager.status()['kind'],'trialExpired')
 def test_restarting_and_clock_rollback_dont_restart_trial(self):
  anchors=MemoryAnchors();manager=self.manager(anchors);self.now+=7200;manager.status()
  again=LicenseManager(anchors,DEVICE,lambda:self.now,VERIFY);self.assertEqual(again.status()['remaining'],TRIAL_SECONDS-7200)
  self.now-=3600;self.assertEqual(again.status()['kind'],'clockError');self.assertFalse(again.allowed())
 def test_anchor_merge_uses_earliest_start_and_latest_seen(self):
  anchors=MemoryAnchors();anchors.values=[dict(version=1,device=DEVICE,start=900000,seen=950000,token=''),dict(version=1,device=DEVICE,start=910000,seen=1000000,token='')]
  manager=self.manager(anchors);self.assertEqual(manager.state['start'],900000)
 def test_malformed_anchor_fails_closed_but_valid_license_recovers(self):
  anchors=MemoryAnchors();anchors.values=[{'version':8}];manager=self.manager(anchors)
  self.assertFalse(manager.allowed());manager.activate(sign());self.assertTrue(manager.allowed())
 def test_signed_device_binding_and_tampering(self):
  token=sign();self.assertEqual(VERIFY(token,DEVICE)['customer'],'Test customer')
  with self.assertRaises(ValueError):VERIFY(token,'BH-'+'B'*32)
  parts=token.split('.');raw=base64.urlsafe_b64decode(parts[1]+'='*((-len(parts[1]))%4));parts[1]=b64(raw.replace(b'Test customer',b'Fake customer'))
  with self.assertRaises(ValueError):VERIFY('.'.join(parts),DEVICE)
  for invalid in ['','BH1.a.a','BH1.'+'a'*7000,token[:-20]]:
   with self.assertRaises(ValueError):VERIFY(invalid,DEVICE)
 def test_licensed_activation_survives_expiry_and_restart(self):
  anchors=MemoryAnchors();manager=self.manager(anchors);manager.activate(sign());self.now+=TRIAL_SECONDS*10
  again=LicenseManager(anchors,DEVICE,lambda:self.now,VERIFY);self.assertEqual(again.status()['kind'],'licensed')
 def test_storage_failure_blocks_trial(self):
  anchors=MemoryAnchors()
  with patch.object(anchors,'write',side_effect=OSError('denied')):
   self.assertFalse(self.manager(anchors).allowed())
 def test_activation_must_be_persisted_before_unlock(self):
  manager=self.manager()
  with patch.object(manager.backend,'write',side_effect=OSError('denied')):
   with self.assertRaises(OSError):manager.activate(sign())
  # Failed persistence must never unlock this process either.
  self.assertNotEqual(manager.status()['kind'],'licensed')

@unittest.skipUnless(os.name=='nt','Windows DPAPI')
class NativeLicenseTests(unittest.TestCase):
 def test_dpapi_roundtrip_and_tamper(self):
  raw=b'BackHere native license test';encoded=protect(raw);self.assertNotEqual(encoded,raw);self.assertEqual(protect(encoded,decrypt=True),raw)
  damaged=bytearray(encoded);damaged[-1]^=1
  with self.assertRaises(OSError):protect(bytes(damaged),decrypt=True)
 def test_profile_registry_anchors_roundtrip(self):
  # The production registry path is never touched by tests.
  import winreg
  import licensing
  path=r'Software\RainyStudio\BackHere-Test-'+__import__('uuid').uuid4().hex
  with tempfile.TemporaryDirectory() as folder,patch.object(licensing,'REGISTRY_PATH',path):
   try:
    anchors=WindowsAnchors(folder);manager=LicenseManager(anchors,device_id())
    self.assertEqual(manager.status()['kind'],'trial');self.assertEqual(len(anchors.read()),2)
    anchors.path.unlink();again=LicenseManager(anchors,device_id());self.assertEqual(again.state['start'],manager.state['start'])
   finally:
    try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
    except FileNotFoundError:pass
