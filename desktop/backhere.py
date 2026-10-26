"""BackHere Windows desktop application, Python 3.11+, standard library only."""
import ctypes
import json
import os
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from core import Store, open_target
from windows import Hotkey, explorer_selection

BG = '#f7f7f2'
PANEL = '#eeeee7'
GREEN = '#486342'
TEXT = '#293324'
MUTED = '#7c8871'


class App:
    def __init__(self, root):
        self.root = root
        self.root.title('BackHere')
        root.geometry('1080x720')
        root.minsize(780, 540)
        root.configure(bg=BG)
        base = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'BackHere'
        self.store = Store(base / 'backhere.sqlite3')
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
        self.hotkey = Hotkey(self.events)
        root.after(100, self.poll)
        root.bind('<Control-n>', lambda _: self.edit())
        root.bind('<Control-f>', lambda _: self.search_entry.focus_set())
        root.protocol('WM_DELETE_WINDOW', self.exit)

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
        self.label(sidebar, self.t('private'), 9, MUTED, wraplength=160, justify='left').pack(side='bottom', fill='x', pady=16)
        ttk.Button(sidebar, text=self.t('import'), command=self.import_data).pack(side='bottom', fill='x', pady=4)
        ttk.Button(sidebar, text=self.t('export'), command=self.export_data).pack(side='bottom', fill='x', pady=4)
        main = tk.Frame(shell, bg=BG, padx=28, pady=22)
        main.pack(side='left', fill='both', expand=True)
        top = tk.Frame(main, bg=BG)
        top.pack(fill='x')
        self.label(top, 'WINDOWS DESKTOP  /  v0.1', 9, MUTED).pack(side='left')
        self.language = ttk.Combobox(top, state='readonly', values=list(self.locales['names'].values()), width=15)
        self.language.set(self.locales['names'][self.lang])
        self.language.pack(side='right')
        self.language.bind('<<ComboboxSelected>>', self.change_language)
        self.label(main, self.t('headline'), 26, TEXT, anchor='w', wraplength=700, justify='left').pack(fill='x', pady=(30, 5))
        self.label(main, self.t('subtitle'), 10, MUTED, anchor='w', wraplength=700).pack(fill='x', pady=(0, 20))
        tools = tk.Frame(main, bg=BG)
        tools.pack(fill='x', pady=(0, 15))
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
        for key, fn in [('resume', self.resume), ('edit', self.edit_selected), ('pin', self.pin), ('complete', self.complete), ('delete', self.delete)]:
            ttk.Button(actions, text=self.t(key), command=fn).pack(side='left', padx=(0, 5))
        self.status = self.label(main, 'Ctrl+N · Ctrl+F · Ctrl+Alt+B', 9, MUTED, anchor='w')
        self.status.pack(fill='x', pady=(15, 0))
        self.search.set(old_query)
        self.render()

    def change_language(self, _):
        name = self.language.get()
        self.lang = next(k for k, v in self.locales['names'].items() if v == name)
        self.store.set_setting('language', self.lang)
        self.build()

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
            except (ValueError, OSError) as exc:
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
            except (OSError, ValueError) as exc:
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

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'capture':
                # Resolve Explorer path off the UI thread, before bringing BackHere forward.
                def resolve(source=value):
                    source['target'] = explorer_selection(source.get('hwnd'))
                    self.events.put(('capture_ready', source))
                threading.Thread(target=resolve, daemon=True).start()
            elif kind == 'capture_ready':
                self.root.deiconify()
                self.root.lift()
                self.root.attributes('-topmost', True)
                self.root.after(150, lambda: self.root.attributes('-topmost', False))
                self.edit(capture=value)
            elif kind == 'hotkey_error':
                self.status.config(text='Ctrl+N · Ctrl+F | '+value)
            elif kind == 'hotkey_ready':
                self.hotkey_ok = True
        self.root.after(100, self.poll)

    def exit(self):
        self.hotkey.stop()
        self.store.close()
        self.root.destroy()


if __name__ == '__main__':
    if os.name == 'nt':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    app = App(root)
    root.mainloop()
