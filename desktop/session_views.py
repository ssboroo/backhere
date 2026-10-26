"""Workspace capture/review/restore UI. Workers only communicate through App.events."""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from design import Button,color,font,icon
from session_model import merge_browser_export
from session_windows import capture_workspace,restore_workspace,hibernate_windows


class SessionView:
    def show_sessions(self):
        win=self.modal(self.t('sessions'),'920x710')
        if not win:return
        win.minsize(820,560)
        self.session_window=win
        self.session_selected=None
        self.session_checks={}
        win.grid_columnconfigure(0,weight=1);win.grid_rowconfigure(2,weight=1)
        header=ctk.CTkFrame(win,fg_color='transparent');header.grid(row=0,column=0,sticky='ew',padx=24,pady=(22,8))
        self.text(header,self.t('sessions'),24,bold=True).pack(side='left')
        Button(header,kind='ghost',symbol='close',text='',width=32,height=32,command=self.close_sessions).pack(side='right')
        toolbar=ctk.CTkFrame(win,fg_color='transparent');toolbar.grid(row=1,column=0,sticky='ew',padx=24,pady=(0,14))
        toolbar.grid_columnconfigure(0,weight=1)
        self.session_name=ctk.CTkEntry(toolbar,height=40,font=font(13),fg_color=color('raised'),border_color=color('border'),text_color=color('text'))
        self.session_name.insert(0,datetime.now().strftime('%Y-%m-%d %H:%M'))
        self.session_name.grid(row=0,column=0,sticky='ew',padx=(0,10))
        self.capture_session_button=Button(toolbar,kind='primary',symbol='plus',text=self.t('saveWorkspace'),command=self.capture_session)
        self.capture_session_button.grid(row=0,column=1)
        self.auto_session_variable=tk.BooleanVar(value=self.store.setting('auto_workspace','0')=='1')
        ctk.CTkCheckBox(toolbar,text=self.t('autoWorkspace'),variable=self.auto_session_variable,font=font(11),text_color=color('muted'),command=lambda:self.store.set_setting('auto_workspace','1' if self.auto_session_variable.get() else '0')).grid(row=1,column=0,columnspan=2,sticky='w',pady=(12,0))
        body=ctk.CTkFrame(win,fg_color='transparent');body.grid(row=2,column=0,sticky='nsew',padx=24)
        body.grid_columnconfigure(1,weight=1);body.grid_rowconfigure(0,weight=1)
        self.session_list=ctk.CTkScrollableFrame(body,width=230,fg_color=color('raised'),scrollbar_button_color=color('border'))
        self.session_list.grid(row=0,column=0,sticky='ns',padx=(0,18))
        self.session_details=ctk.CTkScrollableFrame(body,fg_color='transparent',scrollbar_button_color=color('border'))
        self.session_details.grid(row=0,column=1,sticky='nsew')
        footer=ctk.CTkFrame(win,fg_color='transparent');footer.grid(row=3,column=0,sticky='ew',padx=24,pady=(14,20))
        footer.grid_columnconfigure(0,weight=1)
        self.session_status=self.text(footer,self.t('sessionLimits'),11,'muted',wraplength=520,justify='left',anchor='w')
        self.session_status.grid(row=0,column=0,sticky='ew')
        Button(footer,kind='secondary',symbol='moon',text=self.t('hibernate'),command=self.request_hibernate).grid(row=0,column=1,padx=(12,0))
        win.protocol('WM_DELETE_WINDOW',self.close_sessions)
        win.bind('<Escape>',lambda _:self.close_sessions())
        self.refresh_sessions()

    def close_sessions(self):
        if getattr(self,'workspace_restore_busy',False):self.workspace_cancel.set()
        if getattr(self,'session_window',None) and self.session_window.winfo_exists():self.session_window.destroy()

    def refresh_sessions(self,selected=None):
        if not getattr(self,'session_window',None) or not self.session_window.winfo_exists():return
        for child in self.session_list.winfo_children():child.destroy()
        sessions=self.store.sessions.all()
        if selected:self.session_selected=selected
        elif self.session_selected not in {s['id'] for s in sessions}:self.session_selected=sessions[0]['id'] if sessions else None
        for snapshot in sessions:
            name=snapshot['name'][:26];count=len(snapshot['windows'])
            Button(self.session_list,kind='ghost',symbol='folder',text=f'{name}\n{count} {self.t("windows")}',height=60,anchor='w',fg_color=color('selected') if snapshot['id']==self.session_selected else 'transparent',command=lambda sid=snapshot['id']:self.select_session(sid)).pack(fill='x',pady=3)
        self.select_session(self.session_selected)

    def select_session(self,session_id):
        if self.workspace_restore_busy:return
        self.session_selected=session_id
        for child in self.session_details.winfo_children():child.destroy()
        self.session_checks={}
        snapshot=self.store.sessions.get(session_id) if session_id else None
        if not snapshot:
            self.text(self.session_details,self.t('sessionEmpty'),17,'muted',wraplength=480,justify='left').pack(fill='x',pady=40)
            return
        self.text(self.session_details,snapshot['name'],19,bold=True,wraplength=480,anchor='w',justify='left').pack(fill='x',pady=(5,5))
        self.text(self.session_details,snapshot['machine']+' · '+datetime.fromtimestamp(snapshot['created']).strftime('%Y-%m-%d %H:%M'),11,'muted',anchor='w').pack(fill='x',pady=(0,12))
        self.text(self.session_details,self.t('sessionLimits'),12,'muted',wraplength=480,justify='left',anchor='w').pack(fill='x',pady=(0,12))
        actions=ctk.CTkFrame(self.session_details,fg_color='transparent');actions.pack(fill='x',pady=(0,14))
        self.restore_session_button=Button(actions,kind='primary',symbol='restore',text=self.t('restoreWorkspace'),command=self.restore_session)
        self.restore_session_button.pack(side='left',padx=(0,8))
        Button(actions,kind='secondary',symbol='folder',text=self.t('importTabs'),command=self.import_session_tabs).pack(side='left')
        for window in snapshot['windows']:
            panel=ctk.CTkFrame(self.session_details,fg_color=color('raised'),corner_radius=8)
            panel.pack(fill='x',pady=(0,8))
            enabled=tk.BooleanVar(value=True);self.session_checks[window['id']]=enabled
            ctk.CTkCheckBox(panel,text=window['title'][:70],variable=enabled,font=font(12,'bold'),text_color=color('text')).pack(fill='x',padx=12,pady=(12,6))
            details=window['target'] or window['exe'] or window['app']
            self.text(panel,details,11,'muted',wraplength=450,anchor='w',justify='left').pack(fill='x',padx=12,pady=(0,5))
            coverage=self.t('tabs')+': '+str(len(window['tabs'])) if window['tabs'] else self.t('appOnly') if not window['target'] else self.t('targetAndLayout')
            if window['unsaved']:coverage+=' · '+self.t('unsavedState')
            self.text(panel,coverage,11,'danger' if window['unsaved'] else 'accent',wraplength=450,anchor='w',justify='left').pack(fill='x',padx=12,pady=(0,12))
        if snapshot['warnings']:
            self.text(self.session_details,'\n'.join(snapshot['warnings']),11,'muted',wraplength=480,justify='left',anchor='w').pack(fill='x',pady=10)
        Button(self.session_details,kind='ghost',symbol='trash',text=self.t('delete'),text_color=color('danger'),command=self.delete_session).pack(anchor='w',pady=10)
        self.session_log=ctk.CTkTextbox(self.session_details,height=110,fg_color=color('raised'),text_color=color('text'),font=font(11),wrap='word')
        self.session_log.pack(fill='x',pady=(0,12));self.session_log.configure(state='disabled')

    def capture_session(self,automatic=False):
        if self.workspace_capture_busy or self.workspace_restore_busy:return
        name='Auto '+datetime.now().strftime('%Y-%m-%d %H:%M') if automatic else (self.session_name.get().strip() if getattr(self,'session_window',None) and self.session_window.winfo_exists() else datetime.now().strftime('%Y-%m-%d %H:%M'))
        if not name or len(name)>160:
            messagebox.showerror('BackHere',self.t('title'));return
        self.workspace_capture_busy=True
        self.status.configure(text=self.t('capturingWorkspace'))
        if getattr(self,'capture_session_button',None) and self.capture_session_button.winfo_exists():self.capture_session_button.configure(state='disabled')
        def worker():
            try:
                snapshot=capture_workspace(name);snapshot['automatic']=automatic
                self.events.put(('workspace_captured',snapshot))
            except Exception as exc:self.events.put(('workspace_capture_error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def auto_capture_session(self):
        if self.closing:return
        if not self.testing and self.store.setting('auto_workspace','0')=='1':self.capture_session(automatic=True)
        self.root.after(300000,self.auto_capture_session)

    def import_session_tabs(self):
        if self.workspace_restore_busy or self.workspace_capture_busy:return
        snapshot=self.store.sessions.get(self.session_selected) if self.session_selected else None
        if not snapshot:return
        path=filedialog.askopenfilename(parent=self.session_window,filetypes=[('BackHere browser JSON','*.json')])
        if not path:return
        try:
            if Path(path).stat().st_size>5_000_000:raise ValueError('Browser export too large')
            merged=merge_browser_export(snapshot,json.loads(Path(path).read_text('utf-8')))
            self.store.sessions.save(merged);self.refresh_sessions(merged['id'])
        except (ValueError,OSError,sqlite3.Error) as exc:messagebox.showerror('BackHere',str(exc),parent=self.session_window)

    def restore_session(self):
        if self.workspace_restore_busy or self.workspace_capture_busy:return
        snapshot=self.store.sessions.get(self.session_selected) if self.session_selected else None
        selected={key for key,var in self.session_checks.items() if var.get()}
        if not snapshot or not selected:return
        if not messagebox.askyesno('BackHere',self.t('restoreWorkspaceConfirm'),parent=self.session_window):return
        self.workspace_restore_busy=True;self.workspace_cancel.clear()
        self.restore_session_button.configure(text=self.t('stop'),command=self.workspace_cancel.set)
        def worker():
            try:
                reports=restore_workspace(snapshot,selected,self.workspace_cancel,lambda report:self.events.put(('workspace_progress',report)))
                self.events.put(('workspace_restored',reports))
            except Exception as exc:self.events.put(('workspace_restore_error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()

    def delete_session(self):
        if self.workspace_restore_busy:return
        if self.session_selected and messagebox.askyesno('BackHere',self.t('delete')+'?',parent=self.session_window):
            self.store.sessions.delete(self.session_selected);self.refresh_sessions()

    def request_hibernate(self):
        if self.workspace_restore_busy or self.workspace_capture_busy:return
        if not messagebox.askyesno('BackHere',self.t('hibernateConfirm'),parent=getattr(self,'session_window',None) or self.root):return
        try:
            self.store.daily_backup(self.data_dir/'backups',force=True)
            hibernate_windows()
        except (OSError,sqlite3.Error) as exc:messagebox.showerror('BackHere',str(exc),parent=self.root)

    def handle_workspace_event(self,kind,value):
        if kind=='workspace_captured':
            self.workspace_capture_busy=False
            self.store.sessions.save(value)
            automatic=[s for s in self.store.sessions.all() if s.get('automatic')]
            for old in automatic[20:]:self.store.sessions.delete(old['id'])
            self.status.configure(text=self.t('saved')+' · '+str(len(value['windows']))+' '+self.t('windows'))
            self.refresh_sessions(value['id'])
        elif kind=='workspace_capture_error':
            self.workspace_capture_busy=False;self.status.configure(text=self.t('error')+' · '+value)
        elif kind=='workspace_progress':
            box=getattr(self,'session_log',None)
            if box is not None and box.winfo_exists():
                box.configure(state='normal');box.insert('end',value['state']+' · '+value['title']+'\n'+value['detail']+'\n\n');box.see('end');box.configure(state='disabled')
        elif kind in ('workspace_restored','workspace_restore_error'):
            self.workspace_restore_busy=False
            button=getattr(self,'restore_session_button',None)
            if button is not None and button.winfo_exists():button.configure(text=self.t('restoreWorkspace'),command=self.restore_session)
            self.status.configure(text=self.t('restoreFinished') if kind=='workspace_restored' else self.t('error')+' · '+value)
        if not self.workspace_capture_busy:
            button=getattr(self,'capture_session_button',None)
            if button is not None and button.winfo_exists():button.configure(state='normal')
