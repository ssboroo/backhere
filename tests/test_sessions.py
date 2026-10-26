import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from session_model import new_snapshot,validate_snapshot,launch_plan,clamp_rectangle,imported_snapshot,merge_browser_export
from core import Store
import session_windows as native

def window(**changes):
 value=dict(id='w1',title='Example',exe=r'C:\Apps\example.exe',app='example.exe',target='',position='',kind='app',show=1,rect=[50,50,800,600],hwnd=123,pid=456,started=789,unsaved=False,tabs=[])
 value.update(changes);return value

class SessionTests(unittest.TestCase):
 def test_schema_rejects_bad_identity_geometry_and_urls(self):
  for update in [dict(rect=[0,0,0,100]),dict(pid=-1),dict(unsaved='yes'),dict(tabs=[dict(url='javascript:alert(1)')])]:
   with self.assertRaises(ValueError):new_snapshot('Test',[window(**update)])
  with self.assertRaises(ValueError):new_snapshot('Test',[window(),window()])
 def test_import_discards_machine_identity(self):
  original=new_snapshot('Test',[window()]);result=imported_snapshot(original)
  self.assertEqual(result['windows'][0]['hwnd'],0);self.assertEqual(original['windows'][0]['hwnd'],123)
 def test_launch_never_replays_commands(self):
  for exe in [r'C:\Windows\cmd.exe',r'C:\Windows\powershell.exe','example.exe',r'C:\WindowsApps\app.exe']:
   self.assertEqual(launch_plan(window(exe=exe))['action'],'manual')
  target='https://example.com/?q=--incognito&x=1'
  plan=launch_plan(window(kind='browser',exe=r'C:\Chrome\chrome.exe',target=target))
  self.assertEqual(plan['argv'],[r'C:\Chrome\chrome.exe','--new-window',target])
 def test_monitor_removed_and_negative_monitor(self):
  self.assertEqual(clamp_rectangle([2500,200,3500,1000],[[0,0,1920,1040]]),[920,200,1920,1000])
  self.assertEqual(clamp_rectangle([-1800,100,-800,900],[[-1920,0,0,1040],[0,0,1920,1040]]),[-1800,100,-800,900])
 def test_browser_import_cannot_inject_executable(self):
  snapshot=new_snapshot('Browser',[window(exe=r'C:\Chrome\chrome.exe',kind='browser')])
  data=dict(format='backhere-browser',version=1,browser='chrome.exe',windows=[dict(tabs=[dict(url='https://example.com',pinned=True)])])
  result=merge_browser_export(snapshot,data)
  self.assertEqual(result['windows'][0]['exe'],snapshot['windows'][0]['exe'])
  self.assertTrue(result['windows'][0]['tabs'][0]['pinned'])
  data['browser']='cmd.exe'
  with self.assertRaises(ValueError):merge_browser_export(snapshot,data)
 def test_workspace_backup_roundtrip_and_atomic_import(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder);store=Store(base/'source.db');other=Store(base/'other.db')
   try:
    session=new_snapshot('Test',[window()]);store.sessions.save(session)
    output=base/'backup.json';store.export(output);self.assertEqual(other.import_backup(output),1)
    self.assertEqual(other.sessions.get(session['id'])['windows'][0]['hwnd'],0)
    snapshot=store.daily_backup(base/'snapshots');store.sessions.delete(session['id']);store.restore_snapshot(snapshot,base/'before')
    self.assertEqual(len(store.sessions.all()),1)
    invalid=json.loads(output.read_text());invalid['sessions'][0]['windows'][0]['rect']=[0,0,0,0];output.write_text(json.dumps(invalid))
    with self.assertRaises(ValueError):other.import_backup(output)
    self.assertEqual(len(other.sessions.all()),1)
   finally:store.close();other.close()
 def test_restore_reuses_and_preserves_existing_document(self):
  saved=window();snapshot=new_snapshot('Test',[saved]);seen=[]
  with patch.object(native,'enumerate_windows',return_value=[saved]),patch.object(native,'place_window') as move,patch.object(native.subprocess,'Popen') as launch:
   result=native.restore_workspace(snapshot,{'w1'},progress=seen.append)
   self.assertEqual(result[0]['state'],'reused');move.assert_called_once();launch.assert_not_called();self.assertEqual(result,seen)
 def test_cancel_does_not_launch_and_missing_path_reported(self):
  snapshot=new_snapshot('Test',[window(exe=r'C:\missing\app.exe')]);cancel=threading.Event();cancel.set()
  with patch.object(native,'enumerate_windows',return_value=[]),patch.object(native.subprocess,'Popen') as launch:
   self.assertEqual(native.restore_workspace(snapshot,{'w1'},cancel),[])
   result=native.restore_workspace(snapshot,{'w1'});self.assertEqual(result[0]['state'],'failed');launch.assert_not_called()
 def test_hibernate_only_constructs_native_command(self):
  with patch.object(native.os,'name','nt'),patch.object(native,'Path',return_value=__import__('unittest.mock').mock.MagicMock()),patch.object(native.subprocess,'run') as run:
   run.return_value.returncode=0;native.hibernate_windows();self.assertEqual(run.call_args.args[0][-1],'/h')

@unittest.skipUnless(os.name=='nt','Native Windows session APIs')
class NativeSessionTests(unittest.TestCase):
 def test_enumerate_and_position_real_window(self):
  import tkinter as tk
  root=tk.Tk()
  try:
   root.title('BackHere native session test');root.geometry('420x260+90+90');root.update()
   records=native.enumerate_windows();saved=next(w for w in records if w['title']=='BackHere native session test')
   self.assertTrue(saved['exe'].lower().endswith('.exe'));self.assertGreater(saved['started'],0)
   native.place_window(saved['hwnd'],[150,150,650,500],1);root.update()
   updated=next(w for w in native.enumerate_windows() if w['hwnd']==saved['hwnd'])
   self.assertLess(abs(updated['rect'][0]-150),10);self.assertTrue(native.workareas())
  finally:root.destroy()
