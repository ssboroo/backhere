"""BackHere Windows desktop application, Python 3.12+, native Windows UI."""
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import sqlite3
import struct
import tempfile
import os
import queue
import sys
import threading
import tkinter as tk
import customtkinter as ctk
from views import WorkspaceView
from session_views import SessionView
from design import color
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from core import Store, open_target
from windows import Hotkey, capture_target, parse_hotkey, set_startup, startup_enabled, SingleInstance, ShowSignal, signal_existing

VERSION = "0.5.1"

class App(WorkspaceView, SessionView):
    def __init__(self, root, testing=False):
        self.version = VERSION
        self.root = root
        self.testing = testing
        self.closing = False
        self.tray = None
        self.capture_pending = False
        self.workspace_capture_busy = False
        self.workspace_restore_busy = False
        self.workspace_cancel = threading.Event()
        self.show_signal = ShowSignal() if not testing else None
        self.root.title('BackHere')
        scale = root._get_window_scaling()
        width = min(1240, max(860, int(root.winfo_screenwidth()/scale)-64))
        height = min(790, max(560, int(root.winfo_screenheight()/scale)-90))
        root.geometry(f'{width}x{height}')
        root.minsize(860, 560)
        root.configure(fg_color=color('background'))
        icon = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'backhere.ico'
        if icon.exists():
            root.iconbitmap(str(icon))
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'BackHere'
        self.data_dir = base
        self.store = Store(base / 'backhere.sqlite3')
        self.root.report_callback_exception = self.report_error
        self.backup_error = None
        try:
            self.store.daily_backup(base / 'backups')
        except (OSError, sqlite3.Error) as exc:
            self.backup_error = str(exc)
            logging.exception('Startup backup failed')
        resource = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        self.locales = json.loads((resource / 'locales.json').read_text(encoding='utf-8'))
        self.lang = self.store.setting('language', 'mn')
        if self.lang not in self.locales['rows']:
            self.lang = 'mn'
        self.filter = 'active'
        self.search = tk.StringVar()
        self.sort = tk.StringVar(value='new')
        self.dialog = None
        self.events = queue.Queue()
        self.hotkey_ok = False
        self.style()
        self.build()
        self.shortcut = self.store.setting('hotkey', 'Ctrl+Alt+B')
        try:
            parse_hotkey(self.shortcut)
        except ValueError:
            self.shortcut = 'Ctrl+Alt+B'
        self.hotkey = Hotkey(self.events, self.shortcut) if not testing else None
        self.start_tray()
        root.after(100, self.poll)
        root.bind('<Configure>', self.on_resize, add='+')
        root.bind('<Control-n>', lambda _: self.edit())
        root.bind('<Control-f>', lambda _: self.search_entry.focus_set())
        root.protocol('WM_DELETE_WINDOW', self.close_window)
        if self.backup_error:
            self.status.configure(text=self.t('error')+' — '+self.t('backups'))
        root.after(60000, self.periodic_backup)
        root.after(300000, self.auto_capture_session)

    def t(self, key):
        try:
            return self.locales['rows'][self.lang][self.locales['keys'].index(key)]
        except (ValueError, IndexError, KeyError):
            return key

    def browse(self, fields):
        path = filedialog.askopenfilename(parent=self.dialog)
        if path:
            fields['target'].delete(0, 'end')
            fields['target'].insert(0, path)
            if not fields['title'].get():
                fields['title'].insert(0, Path(path).name)

    def resume(self):
        item = self.selected()
        if item:
            try:
                open_target(item['target'], item['position'])
            except (OSError, ValueError, sqlite3.Error) as exc:
                messagebox.showerror('BackHere', str(exc), parent=self.root)

    def pin(self):
        item = self.selected()
        if item:
            self.store.flag(item['id'], 'pinned', not item['pinned'])
            self.render()

    def complete(self):
        item = self.selected()
        if item:
            self.store.flag(item['id'], 'done', not item['done'])
            self.render()

    def delete(self):
        item = self.selected()
        if item and item['done'] and messagebox.askyesno('BackHere', self.t('delete')+' — '+item['title']+'?', parent=self.root):
            self.store.delete(item['id'])
            self.render()

    def export_data(self):
        path = filedialog.asksaveasfilename(defaultextension='.json', initialfile='BackHere-'+datetime.now().strftime('%Y-%m-%d')+'.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.store.export(path)
                self.status.configure(text=self.t('saved'))
            except OSError as exc:
                messagebox.showerror('BackHere', str(exc))

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.store.import_backup(path)
                self.render()
                self.status.configure(text=self.t('saved'))
            except (OSError, ValueError, KeyError) as exc:
                messagebox.showerror('BackHere', self.t('invalid')+'\n'+str(exc))

    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(150, lambda: self.root.attributes('-topmost', False))

    def start_tray(self):
        if self.testing or os.name != 'nt':
            return
        try:
            from tray import Tray
            self.tray = Tray(self.events, {k: self.t(k) for k in ('show', 'new', 'exit')})
        except Exception:
            logging.exception('Tray unavailable; close will exit normally')
            self.tray = None

    def close_window(self):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        if self.tray and self.tray.visible and self.store.setting('close_tray', '1') == '1':
            self.root.withdraw()
        else:
            self.exit()

    def backup_now(self):
        path = filedialog.asksaveasfilename(parent=self.dialog or self.root, defaultextension='.json', initialfile='BackHere-'+datetime.now().strftime('%Y-%m-%d')+'.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.store.export(path)
                self.status.configure(text=self.t('backupSaved'))
            except (OSError, sqlite3.Error) as exc:
                messagebox.showerror('BackHere', str(exc))

    def restore_backup(self):
        path = filedialog.askopenfilename(parent=self.dialog or self.root, initialdir=self.data_dir / 'backups', filetypes=[('BackHere SQLite', '*.sqlite3')])
        if not path:
            return
        if not messagebox.askyesno('BackHere', self.t('restoreConfirm'), parent=self.dialog or self.root):
            return
        try:
            self.store.restore_snapshot(path, self.data_dir / 'backups')
            self.render()
            self.status.configure(text=self.t('saved'))
        except (OSError, ValueError, sqlite3.Error) as exc:
            messagebox.showerror('BackHere', self.t('invalid')+'\n'+str(exc))

    def periodic_backup(self):
        if self.closing:
            return
        try:
            self.store.daily_backup(self.data_dir / 'backups', force=True)
        except (OSError, sqlite3.Error):
            logging.exception('Daily backup failed')
            self.status.configure(text=self.t('error')+' — '+self.t('backups'))
        self.root.after(60000, self.periodic_backup)

    def report_error(self, exc_type, value, tb):
        logging.error('UI exception', exc_info=(exc_type, value, tb))
        messagebox.showerror('BackHere', self.t('error')+'\n'+str(value), parent=self.root)

    def poll(self):
        if self.closing:
            return
        if self.show_signal and self.show_signal.pending():
            self.show()
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind.startswith('workspace_'):
                self.handle_workspace_event(kind,value)
            elif kind == 'capture' and not self.capture_pending:
                self.capture_pending = True
                def resolve(source=value):
                    source.update(capture_target(source))
                    self.events.put(('capture_ready', source))
                threading.Thread(target=resolve, daemon=True).start()
            elif kind == 'capture_ready':
                self.capture_pending = False
                self.show()
                self.edit(capture=value)
                if not value.get('target'):
                    self.status.configure(text=self.t('captureMissing'))
            elif kind == 'hotkey_error':
                self.status.configure(text=self.t('hotkeyConflict')+' '+value)
            elif kind == 'hotkey_ready':
                self.hotkey_ok = True
                self.shortcut = value
                self.store.set_setting('hotkey', value)
                self.status.configure(text='Ctrl+N · Ctrl+F · '+value)
            elif kind == 'tray_error':
                self.status.configure(text=self.t('error')+' — '+self.t('closeTray'))
                self.show()
            elif kind == 'show':
                self.show()
            elif kind == 'new':
                self.show()
                self.edit()
            elif kind == 'exit':
                self.exit()
                return
        self.root.after(100, self.poll)

    def exit(self):
        if self.closing:
            return
        self.closing = True
        self.workspace_cancel.set()
        if self.hotkey:
            self.hotkey.stop()
        if self.tray:
            self.tray.stop()
        if self.show_signal:
            self.show_signal.close()
        try:
            self.store.daily_backup(self.data_dir / 'backups', force=True)
        except (OSError, sqlite3.Error):
            logging.exception('Exit backup failed')
        self.store.close()
        self.root.destroy()


def self_test(output):
    """Exercise the actual frozen executable without touching real user data/settings."""
    with tempfile.TemporaryDirectory() as folder:
        os.environ['LOCALAPPDATA'] = folder
        root = ctk.CTk()
        app = App(root, testing=True)
        root.update()
        for language in app.locales['rows']:
            app.lang = language
            app.build()
            root.update()
        app.change_theme('dark')
        root.update()
        app.change_theme('light')
        root.update()
        item = app.store.save(dict(title='Монгол тест', target='https://example.com', note='Next step', project='Test', position='3'))
        app.render()
        app.select_item(item['id'])
        fields = app.edit_selected()
        root.update()
        app.dialog.destroy()
        from session_model import new_snapshot
        snapshot = new_snapshot('Packaged workspace test', [])
        app.store.sessions.save(snapshot)
        app.show_sessions(); root.update(); app.close_sessions()
        assert app.store.sessions.get(snapshot['id'])['name'] == snapshot['name']
        app.store.export(Path(folder) / 'export.json')
        app.store.daily_backup(Path(folder) / 'snapshots')
        count = len(app.store.all())
        app.exit()
        Path(output).write_text(json.dumps({'ok': count == 1, 'bits': struct.calcsize('P') * 8, 'version': VERSION, 'languages': 12}), encoding='utf-8')


def main():
    if '--self-test' in sys.argv:
        self_test(sys.argv[sys.argv.index('--self-test') + 1])
        return
    instance = SingleInstance()
    if instance.already_running:
        signal_existing()
        instance.close()
        return
    base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'BackHere'
    base.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(base / 'backhere.log', maxBytes=500000, backupCount=2, encoding='utf-8')
    logging.basicConfig(handlers=[handler], level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
    root = ctk.CTk()
    try:
        app = App(root)
        if '--background' in sys.argv:
            # Never hide without an operational tray icon.
            root.after(1500, lambda: root.withdraw() if app.tray and app.tray.visible else None)
        root.mainloop()
    except Exception as exc:
        logging.exception('Startup failed')
        messagebox.showerror('BackHere', 'BackHere could not start. Your data has not been deleted.\n'+str(exc))
    finally:
        instance.close()
        logging.shutdown()


if __name__ == '__main__':
    main()
