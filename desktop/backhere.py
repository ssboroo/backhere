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
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from core import Store, open_target
from windows import Hotkey, capture_target, parse_hotkey, set_startup, startup_enabled, SingleInstance, ShowSignal, signal_existing

VERSION = "0.2.0"

BG = '#f7f7f2'
PANEL = '#eeeee7'
GREEN = '#486342'
TEXT = '#293324'
MUTED = '#7c8871'


class App:
    def __init__(self, root, testing=False):
        self.root = root
        self.testing = testing
        self.closing = False
        self.tray = None
        self.capture_pending = False
        self.show_signal = ShowSignal() if not testing else None
        self.root.title('BackHere')
        root.geometry('1080x720')
        root.minsize(780, 540)
        root.configure(bg=BG)
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
        root.bind('<Control-n>', lambda _: self.edit())
        root.bind('<Control-f>', lambda _: self.search_entry.focus_set())
        root.protocol('WM_DELETE_WINDOW', self.close_window)
        if self.backup_error:
            self.status.config(text=self.t('error')+' — '+self.t('backups'))
        root.after(60000, self.periodic_backup)

    def t(self, key):
        try:
            return self.locales['rows'][self.lang][self.locales['keys'].index(key)]
        except (ValueError, IndexError, KeyError):
            return key

    def style(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background=BG, foreground=TEXT)
        style.configure('TButton', padding=(12, 8), borderwidth=0)
        style.map('TButton', background=[('active', '#dce5d3')])
        style.configure('Primary.TButton', background=GREEN, foreground='white', padding=(18, 10))
        style.map('Primary.TButton', background=[('active', '#354f30')])
        style.configure('Treeview', rowheight=46, background='white', fieldbackground='white', borderwidth=0)
        style.configure('Treeview.Heading', padding=(8, 10), background=PANEL, font=('Segoe UI', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#dce5d3')], foreground=[('selected', TEXT)])
        style.configure('TEntry', padding=8)
        style.configure('TCombobox', padding=6)

    def label(self, parent, text, size=10, color=TEXT, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=color, font=('Segoe UI', size), **kwargs)

    def build(self):
        old_query = self.search.get()
        for child in self.root.winfo_children():
            child.destroy()
        shell = tk.Frame(self.root, bg=BG)
        shell.pack(fill='both', expand=True)
        sidebar = tk.Frame(shell, bg=PANEL, width=195, padx=18, pady=25)
        sidebar.pack(side='left', fill='y')
        sidebar.pack_propagate(False)
        self.label(sidebar, '↶ BackHere.', 23, GREEN).pack(anchor='w', pady=(0, 38))
        self.label(sidebar, self.t('workspace'), 9, MUTED).pack(anchor='w', pady=(0, 12))
        for key in ('active', 'pinned', 'done'):
            ttk.Button(sidebar, text=self.t(key), command=lambda k=key: self.set_filter(k)).pack(fill='x', pady=4)
        ttk.Button(sidebar, text=self.t('settings'), command=self.settings).pack(fill='x', pady=(25, 4))
        ttk.Button(sidebar, text=self.t('exit'), command=self.exit).pack(side='bottom', fill='x', pady=4)
        self.label(sidebar, self.t('private'), 9, MUTED, wraplength=160, justify='left').pack(side='bottom', fill='x', pady=16)
        ttk.Button(sidebar, text=self.t('import'), command=self.import_data).pack(side='bottom', fill='x', pady=4)
        ttk.Button(sidebar, text=self.t('export'), command=self.export_data).pack(side='bottom', fill='x', pady=4)
        main = tk.Frame(shell, bg=BG, padx=28, pady=22)
        main.pack(side='left', fill='both', expand=True)
        top = tk.Frame(main, bg=BG)
        top.pack(fill='x')
        self.label(top, 'WINDOWS DESKTOP  /  v'+VERSION, 9, MUTED).pack(side='left')
        self.language = ttk.Combobox(top, state='readonly', values=list(self.locales['names'].values()), width=15)
        self.language.set(self.locales['names'][self.lang])
        self.language.pack(side='right')
        self.language.bind('<<ComboboxSelected>>', self.change_language)
        self.label(main, self.t('headline'), 26, TEXT, anchor='w', wraplength=700, justify='left').pack(fill='x', pady=(30, 5))
        self.label(main, self.t('subtitle'), 10, MUTED, anchor='w', wraplength=700).pack(fill='x', pady=(0, 20))
        tools = tk.Frame(main, bg=BG)
        tools.pack(fill='x', pady=(0, 15))
        self.label(tools, '⌕', 18, MUTED).pack(side='left', padx=(0, 6))
        self.search_entry = ttk.Entry(tools, textvariable=self.search)
        self.search_entry.pack(side='left', fill='x', expand=True, padx=(0, 12))
        self.search_entry.bind('<KeyRelease>', lambda _: self.render())
        ttk.Button(tools, text='+ '+self.t('new'), style='Primary.TButton', command=self.edit).pack(side='right')
        self.count = self.label(main, '', 10, MUTED, anchor='w')
        self.count.pack(fill='x', pady=(0, 8))
        table = tk.Frame(main, bg=BG)
        table.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table, columns=('title', 'project', 'position'), show='headings', selectmode='browse')
        for key, width in [('title', 330), ('project', 110), ('position', 120)]:
            self.tree.heading(key, text=self.t(key), command=lambda k=key: self.order(k))
            self.tree.column(key, width=width, minwidth=70)
        scroll = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.detail())
        self.tree.bind('<Double-1>', lambda _: self.resume())
        self.preview = tk.Text(main, height=4, wrap='word', bg=BG, fg=MUTED, relief='flat', font=('Segoe UI', 10), padx=5, pady=9, state='disabled')
        self.preview.pack(fill='x', pady=(8, 6))
        actions = tk.Frame(main, bg=BG)
        actions.pack(fill='x')
        self.action_buttons = {}
        for key, fn in [('resume', self.resume), ('edit', self.edit_selected), ('pin', self.pin), ('complete', self.complete), ('delete', self.delete)]:
            button = ttk.Button(actions, text=self.t(key), command=fn)
            button.pack(side='left', padx=(0, 5))
            self.action_buttons[key] = button
        self.status = self.label(main, 'Ctrl+N · Ctrl+F · '+self.store.setting('hotkey', 'Ctrl+Alt+B'), 9, MUTED, anchor='w')
        self.status.pack(fill='x', pady=(15, 0))
        self.search.set(old_query)
        self.render()

    def change_language(self, _):
        name = self.language.get()
        self.lang = next(k for k, v in self.locales['names'].items() if v == name)
        self.store.set_setting('language', self.lang)
        self.build()
        if self.tray:
            self.tray.stop()
            self.tray = None
        self.start_tray()

    def set_filter(self, key):
        self.filter = key
        self.render()

    def order(self, key):
        self.sort.set('old' if self.sort.get() == 'new' else 'new')
        self.render()

    def render(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().casefold()
        self.items = {i['id']: i for i in self.store.all()}
        records = list(self.items.values())
        if self.sort.get() == 'old':
            records.reverse()
        count = 0
        for i in records:
            visible = i['done'] if self.filter == 'done' else (not i['done'] and (self.filter != 'pinned' or i['pinned']))
            if visible and query in ' '.join(str(i[k]) for k in ('title', 'note', 'project', 'target', 'position')).casefold():
                self.tree.insert('', 'end', iid=i['id'], values=(('★ ' if i['pinned'] else '') + i['title'], i['project'], i['position']))
                count += 1
        self.count.config(text=f"{self.t(self.filter)}  ·  {count} {self.t('allCount')}")
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected)
        self.detail()

    def selected(self):
        selection = self.tree.selection()
        return self.items.get(selection[0]) if selection else None

    def detail(self):
        item = self.selected()
        if hasattr(self, 'action_buttons'):
            for key, button in self.action_buttons.items():
                enabled = bool(item) and (key != 'delete' or item['done'])
                button.state(['!disabled'] if enabled else ['disabled'])
            self.action_buttons['complete'].config(text=self.t('restore' if item and item['done'] else 'complete'))
            self.action_buttons['pin'].config(text=self.t('unpin' if item and item['pinned'] else 'pin'))
        self.preview.config(state='normal')
        self.preview.delete('1.0', 'end')
        if item:
            self.preview.insert('1.0', item['target']+'\n'+item['note'])
        self.preview.config(state='disabled')

    def edit_selected(self):
        if self.selected():
            self.edit(self.selected())

    def edit(self, item=None, capture=None):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        win = self.dialog = tk.Toplevel(self.root)
        win.title(self.t('edit') if item else self.t('new'))
        win.configure(bg=BG, padx=24, pady=20)
        win.geometry('600x635')
        win.minsize(490, 560)
        win.transient(self.root)
        if self.lang == 'ar':
            win.option_add('*Entry.justify', 'right')
        win.grab_set()
        win.columnconfigure(0, weight=1)
        fields = {}
        source = item or capture or {}
        for row, key in enumerate(('title', 'target', 'project', 'position')):
            self.label(win, self.t(key), 10, MUTED, anchor='w').grid(row=row*2, column=0, sticky='ew', pady=(8, 3))
            entry = ttk.Entry(win)
            entry.insert(0, source.get(key, ''))
            entry.grid(row=row*2+1, column=0, sticky='ew')
            fields[key] = entry
            if key == 'target':
                ttk.Button(win, text='…', width=3, command=lambda: self.browse(fields)).grid(row=row*2+1, column=1, padx=(5, 0))
        self.label(win, self.t('note'), 10, MUTED, anchor='w').grid(row=8, column=0, sticky='ew', pady=(14, 4))
        note = tk.Text(win, height=5, wrap='word', font=('Segoe UI', 11), relief='solid', bd=1, padx=8, pady=8)
        note.insert('1.0', source.get('note', ''))
        note.grid(row=9, column=0, columnspan=2, sticky='nsew')
        win.rowconfigure(9, weight=1)
        # Desktop files open directly; browser-specific copy-path hint is intentionally omitted.
        self.label(win, 'Ctrl+Enter · '+self.t('save'), 9, MUTED).grid(row=10, column=0, sticky='w', pady=12)
        buttons = tk.Frame(win, bg=BG)
        buttons.grid(row=11, column=0, columnspan=2, sticky='e')
        ttk.Button(buttons, text=self.t('cancel'), command=win.destroy).pack(side='left', padx=8)
        def save(_=None):
            data = {k: entry.get().strip() for k, entry in fields.items()}
            data['note'] = note.get('1.0', 'end-1c').strip()
            try:
                self.store.save(data, item)
            except (ValueError, OSError, sqlite3.Error) as exc:
                messagebox.showerror('BackHere', str(exc), parent=win)
                return
            self.render()
            self.status.config(text=self.t('saved'))
            win.destroy()
        ttk.Button(buttons, text=self.t('save'), style='Primary.TButton', command=save).pack(side='left')
        win.bind('<Control-Return>', save)
        win.bind('<Escape>', lambda _: win.destroy())
        (note if capture else fields['title']).focus_set()
        return fields

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
                self.status.config(text=self.t('saved'))
            except OSError as exc:
                messagebox.showerror('BackHere', str(exc))

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.store.import_backup(path)
                self.render()
                self.status.config(text=self.t('saved'))
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

    def settings(self):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        win = self.dialog = tk.Toplevel(self.root)
        win.title(self.t('settings'))
        win.configure(bg=BG, padx=24, pady=22)
        win.transient(self.root)
        win.grab_set()
        win.columnconfigure(0, weight=1)
        auto = tk.BooleanVar(value=startup_enabled())
        tray = tk.BooleanVar(value=self.store.setting('close_tray', '1') == '1')
        ttk.Checkbutton(win, text=self.t('startup'), variable=auto).grid(row=0, column=0, sticky='w', pady=8)
        ttk.Checkbutton(win, text=self.t('closeTray'), variable=tray).grid(row=1, column=0, sticky='w', pady=8)
        self.label(win, self.t('shortcutLabel'), 10, MUTED).grid(row=2, column=0, sticky='w', pady=(16, 5))
        shortcut = ttk.Entry(win, width=42)
        shortcut.insert(0, self.store.setting('hotkey', 'Ctrl+Alt+B'))
        shortcut.grid(row=3, column=0, sticky='ew')
        self.label(win, 'Ctrl+Alt+B / Ctrl+Shift+B / Alt+Shift+B', 9, MUTED).grid(row=4, column=0, sticky='w', pady=6)
        ttk.Button(win, text=self.t('backupNow'), command=self.backup_now).grid(row=5, column=0, sticky='ew', pady=5)
        ttk.Button(win, text=self.t('restoreBackup'), command=self.restore_backup).grid(row=6, column=0, sticky='ew', pady=5)
        ttk.Button(win, text=self.t('openData'), command=lambda: os.startfile(self.data_dir)).grid(row=7, column=0, sticky='ew', pady=5)
        self.label(win, f'BackHere {VERSION} · Windows {struct.calcsize("P")*8}-bit', 10, MUTED).grid(row=8, column=0, pady=16)
        def apply():
            requested = shortcut.get().strip()
            try:
                parse_hotkey(requested)
                if auto.get() != startup_enabled():
                    set_startup(auto.get())
                self.store.set_setting('close_tray', '1' if tray.get() else '0')
                if self.hotkey and not self.hotkey.rebind(requested):
                    raise OSError(self.t('hotkeyConflict'))
            except (ValueError, OSError) as exc:
                messagebox.showerror('BackHere', str(exc), parent=win)
                return
            win.destroy()
        ttk.Button(win, text=self.t('save'), style='Primary.TButton', command=apply).grid(row=9, column=0, sticky='e')

    def backup_now(self):
        path = filedialog.asksaveasfilename(parent=self.dialog or self.root, defaultextension='.json', initialfile='BackHere-'+datetime.now().strftime('%Y-%m-%d')+'.json', filetypes=[('JSON', '*.json')])
        if path:
            try:
                self.store.export(path)
                self.status.config(text=self.t('backupSaved'))
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
            self.status.config(text=self.t('saved'))
        except (OSError, ValueError, sqlite3.Error) as exc:
            messagebox.showerror('BackHere', self.t('invalid')+'\n'+str(exc))

    def periodic_backup(self):
        if self.closing:
            return
        try:
            self.store.daily_backup(self.data_dir / 'backups', force=True)
        except (OSError, sqlite3.Error):
            logging.exception('Daily backup failed')
            self.status.config(text=self.t('error')+' — '+self.t('backups'))
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
            if kind == 'capture' and not self.capture_pending:
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
                    self.status.config(text=self.t('captureMissing'))
            elif kind == 'hotkey_error':
                self.status.config(text=self.t('hotkeyConflict')+' '+value)
            elif kind == 'hotkey_ready':
                self.hotkey_ok = True
                self.shortcut = value
                self.store.set_setting('hotkey', value)
                self.status.config(text='Ctrl+N · Ctrl+F · '+value)
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
        root = tk.Tk()
        app = App(root, testing=True)
        root.update()
        for language in app.locales['rows']:
            app.lang = language
            app.build()
            root.update()
        item = app.store.save(dict(title='Монгол тест', target='https://example.com', note='Next step', project='Test', position='3'))
        app.render()
        app.tree.selection_set(item['id'])
        app.detail()
        fields = app.edit_selected()
        root.update()
        app.dialog.destroy()
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
    if os.name == 'nt':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
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
