"""Native desktop presentation, independent of SQLite and Windows integration."""
import os
import sqlite3
import struct
from datetime import datetime
from urllib.parse import urlsplit
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from design import Button, color, font, icon
from windows import parse_hotkey, set_startup, startup_enabled


class WorkspaceView:
    def text(self, parent, text, size=13, tone='text', bold=False, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color(tone), font=font(size,'bold' if bold else 'normal'), **kwargs)

    def style(self):
        ctk.set_default_color_theme('green')
        mode = self.store.setting('appearance','system')
        self.appearance = mode if mode in ('light','dark','system') else 'system'
        ctk.set_appearance_mode(self.appearance)
        self.root.configure(fg_color=color('background'))

    def build(self):
        if getattr(self, 'search_job', None):
            self.root.after_cancel(self.search_job)
            self.search_job = None
        for child in self.root.winfo_children():
            child.destroy()
        self.cards = {}
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        self.sidebar = ctk.CTkFrame(self.root, width=216, corner_radius=0, fg_color=color('sidebar'))
        self.sidebar.grid(row=0,column=0,sticky='ns')
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0,weight=1)
        self.sidebar.grid_rowconfigure(5,weight=1)
        brand = ctk.CTkFrame(self.sidebar,fg_color='transparent')
        brand.grid(row=0,column=0,sticky='ew',padx=22,pady=(28,30))
        self.text(brand,'',image=icon('logo',34,'accent')).pack(side='left')
        self.text(brand,'BackHere',22,bold=True).pack(side='left',padx=10)
        self.text(self.sidebar,self.t('workspace'),11,'muted',anchor='w').grid(row=1,column=0,sticky='ew',padx=24,pady=(0,10))
        nav = ctk.CTkFrame(self.sidebar,fg_color='transparent')
        nav.grid(row=2,column=0,sticky='ew',padx=12)
        self.nav_buttons={}
        for key,symbol in [('active','bookmark'),('pinned','pin'),('done','check')]:
            row=ctk.CTkFrame(nav,fg_color='transparent')
            row.pack(fill='x',pady=3)
            b=Button(row,kind='ghost',symbol=symbol,text=self.t(key),height=42,anchor='w',command=lambda k=key:self.set_filter(k))
            b.pack(fill='x')
            self.nav_buttons[key]=b
        self.text(self.sidebar,self.t('projects'),11,'muted',anchor='w').grid(row=3,column=0,sticky='ew',padx=24,pady=(30,8))
        self.project_box=ctk.CTkFrame(self.sidebar,fg_color='transparent')
        self.project_box.grid(row=4,column=0,sticky='ew',padx=12)
        bottom=ctk.CTkFrame(self.sidebar,fg_color='transparent')
        bottom.grid(row=6,column=0,sticky='ew',padx=12,pady=(12,18))
        self.language=ctk.CTkOptionMenu(bottom,values=list(self.locales['names'].values()),command=self.change_language,width=184,height=34,fg_color=color('soft'),button_color=color('soft'),button_hover_color=color('selected'),text_color=color('text'),font=font(12),dropdown_font=font(13),dropdown_fg_color=color('surface'),dropdown_text_color=color('text'))
        self.language.set(self.locales['names'][self.lang])
        self.language.pack(fill='x',padx=4,pady=(0,12))
        Button(bottom,kind='ghost',symbol='settings',text=self.t('settings'),anchor='w',height=36,command=self.settings).pack(fill='x')
        Button(bottom,kind='ghost',symbol='download',text=self.t('export'),anchor='w',height=36,command=self.export_data).pack(fill='x')
        Button(bottom,kind='ghost',symbol='upload',text=self.t('import'),anchor='w',height=36,command=self.import_data).pack(fill='x')
        self.theme_button=Button(bottom,kind='ghost',symbol='moon',text=self.t('dark') if ctk.get_appearance_mode()=='Light' else self.t('light'),anchor='w',height=36,command=self.toggle_theme)
        self.theme_button.pack(fill='x',pady=(4,0))
        self.text(bottom,'●  '+self.t('localOnly'),11,'muted',wraplength=174,justify='left',anchor='w').pack(fill='x',padx=12,pady=(20,0))
        self.content=ctk.CTkFrame(self.root,fg_color='transparent',corner_radius=0)
        self.content.grid(row=0,column=1,sticky='nsew',padx=28,pady=24)
        self.content.grid_columnconfigure(0,weight=1)
        self.content.grid_rowconfigure(3,weight=1)
        top=ctk.CTkFrame(self.content,fg_color='transparent')
        top.grid(row=0,column=0,sticky='ew')
        top.grid_columnconfigure(0,weight=1)
        self.text(top,self.t('little'),11,'muted',anchor='w').grid(row=0,column=0,sticky='w')
        self.heading=self.text(top,self.t(self.filter),30,bold=True,anchor='w',wraplength=440,justify='left')
        self.heading.grid(row=1,column=0,sticky='w',pady=(7,0))
        Button(top,kind='primary',symbol='plus',text=self.t('new'),width=172,height=44,command=self.edit).grid(row=0,column=1,rowspan=2,sticky='e',padx=(16,0))
        self.text(self.content,self.t('subtitle'),13,'muted',anchor='w',justify='left',wraplength=620).grid(row=1,column=0,sticky='ew',pady=(10,24))
        toolbar=ctk.CTkFrame(self.content,fg_color='transparent')
        toolbar.grid(row=2,column=0,sticky='ew',pady=(0,18))
        toolbar.grid_columnconfigure(0,weight=1)
        self.search_entry=ctk.CTkEntry(toolbar,placeholder_text=self.t('search'),height=42,corner_radius=9,border_width=1,border_color=color('border'),fg_color=color('surface'),text_color=color('text'),font=font(13))
        self.search_entry.grid(row=0,column=0,sticky='ew',padx=(0,12))
        self.search_entry.insert(0,self.search.get())
        self.search_entry.bind('<KeyRelease>',self.queue_search)
        self.sort_menu=ctk.CTkOptionMenu(toolbar,values=[self.t('newest'),self.t('oldest')],command=self.order,width=156,height=42,fg_color=color('surface'),button_color=color('surface'),button_hover_color=color('soft'),text_color=color('muted'),font=font(12),dropdown_font=font(13),dropdown_fg_color=color('surface'),dropdown_text_color=color('text'))
        self.sort_menu.set(self.t('oldest') if self.sort.get()=='old' else self.t('newest'))
        self.sort_menu.grid(row=0,column=1)
        self.body=ctk.CTkFrame(self.content,fg_color='transparent')
        self.body.grid(row=3,column=0,sticky='nsew')
        self.body.grid_columnconfigure(0,weight=1)
        self.body.grid_rowconfigure(1,weight=1)
        self.count=self.text(self.body,'',11,'muted',anchor='w')
        self.count.grid(row=0,column=0,sticky='ew',pady=(0,10))
        self.list_scroll=ctk.CTkScrollableFrame(self.body,fg_color='transparent',corner_radius=0,scrollbar_button_color=color('border'),scrollbar_button_hover_color=color('muted'))
        self.list_scroll.grid(row=1,column=0,sticky='nsew')
        self.list_scroll.grid_columnconfigure(0,weight=1)
        self.inspector=ctk.CTkFrame(self.body,width=304,corner_radius=12,border_width=1,border_color=color('border'),fg_color=color('surface'))
        self.inspector.grid(row=0,column=1,rowspan=2,sticky='nsew',padx=(20,0))
        self.inspector.grid_propagate(False)
        self.status=self.text(self.content,self.t('ready'),11,'muted',anchor='w')
        self.status.grid(row=4,column=0,sticky='ew',pady=(18,0))
        self.root.bind('<Configure>',self.on_resize)
        self.compact=False
        self.project_filter=getattr(self,'project_filter','')
        self.render()
        self.root.after_idle(self.update_layout)

    def queue_search(self,_=None):
        self.search.set(self.search_entry.get())
        if getattr(self,'search_job',None):
            self.root.after_cancel(self.search_job)
        self.search_job=self.root.after(130,self.run_search)

    def run_search(self):
        self.search_job=None
        self.render()

    def on_resize(self,event):
        if event.widget is self.root:
            if getattr(self,'resize_job',None):self.root.after_cancel(self.resize_job)
            self.resize_job=self.root.after(100,self.update_layout)

    def update_layout(self):
        self.resize_job=None
        if self.closing:return
        # Logical rather than physical pixels keeps the breakpoint correct at 125/150% DPI.
        scale=self.root._get_window_scaling()
        logical_width=self.root.winfo_width()/scale
        self.heading.configure(wraplength=max(220,min(440,int(logical_width-460))))
        self.compact=logical_width<1130
        if self.compact:self.inspector.grid_remove()
        else:self.inspector.grid()

    def change_language(self,value):
        self.lang=next(k for k,v in self.locales['names'].items() if v==value)
        self.store.set_setting('language',self.lang)
        self.build()
        if self.tray:self.tray.stop();self.tray=None
        self.start_tray()

    def change_theme(self,value):
        keys={'light':self.t('light'),'dark':self.t('dark'),'system':self.t('system')}
        mode=next((k for k,v in keys.items() if v==value),value)
        if mode not in keys:return
        self.appearance=mode
        self.store.set_setting('appearance',mode)
        ctk.set_appearance_mode(mode)
        if hasattr(self,'theme_button'):
            self.theme_button.configure(text=self.t('dark') if ctk.get_appearance_mode()=='Light' else self.t('light'),image=icon('moon' if ctk.get_appearance_mode()=='Light' else 'sun'))

    def toggle_theme(self):
        self.change_theme('dark' if ctk.get_appearance_mode()=='Light' else 'light')

    def order(self,value):
        self.sort.set('old' if value==self.t('oldest') else 'new')
        self.render()

    def set_filter(self,key):
        self.filter=key
        self.project_filter=''
        self.selected_id=None
        self.render()

    def set_project(self,name):
        self.project_filter=name
        self.filter='active'
        self.selected_id=None
        self.render()

    def render(self):
        self.items={i['id']:i for i in self.store.all()}
        if self.search_entry.get()!=self.search.get():
            self.search_entry.delete(0,'end');self.search_entry.insert(0,self.search.get())
        query=self.search.get().casefold().strip()
        records=list(self.items.values())
        if self.sort.get()=='old':records.reverse()
        self.visible_ids=[]
        for item in records:
            visible=item['done'] if self.filter=='done' else (not item['done'] and (self.filter!='pinned' or item['pinned']))
            if visible and (not self.project_filter or item['project']==self.project_filter) and query in ' '.join(str(item[k]) for k in ('title','note','project','target','position')).casefold():
                self.visible_ids.append(item['id'])
        if getattr(self,'selected_id',None) not in self.visible_ids:
            self.selected_id=self.visible_ids[0] if self.visible_ids else None
        for child in self.list_scroll.winfo_children():child.destroy()
        self.cards={}
        self.heading.configure(text=self.project_filter or self.t(self.filter))
        self.count.configure(text=f"{len(self.visible_ids)} {self.t('allCount')}")
        for key,b in self.nav_buttons.items():
            count=sum(bool(i['done']) if key=='done' else not i['done'] and (key!='pinned' or i['pinned']) for i in records)
            b.configure(text=f"{self.t(key)}   {count}",fg_color=color('selected') if key==self.filter and not self.project_filter else 'transparent')
        for child in self.project_box.winfo_children():child.destroy()
        projects=sorted({i['project'] for i in records if i['project'] and not i['done']},key=str.casefold)
        for name in projects[:5]:
            Button(self.project_box,kind='ghost',symbol='folder',text=name[:24],anchor='w',height=34,fg_color=color('selected') if name==self.project_filter else 'transparent',command=lambda n=name:self.set_project(n)).pack(fill='x',pady=2)
        if not projects:self.text(self.project_box,'—',12,'muted',anchor='w').pack(fill='x',padx=12)
        for row,item_id in enumerate(self.visible_ids):self.make_card(row,self.items[item_id])
        if not self.visible_ids:self.empty_state(bool(query or self.project_filter))
        self.detail()

    def make_card(self,row,item):
        selected=item['id']==self.selected_id
        card=ctk.CTkFrame(self.list_scroll,corner_radius=11,border_width=1,border_color=color('accent') if selected else color('border'),fg_color=color('selected') if selected else color('surface'))
        card.grid(row=row,column=0,sticky='ew',pady=(0,10),padx=(0,2))
        card.grid_columnconfigure(1,weight=1)
        kind='link' if item['target'].lower().startswith(('https://','http://')) else 'file'
        badge=ctk.CTkFrame(card,width=38,height=38,corner_radius=9,fg_color=color('soft'))
        badge.grid(row=0,column=0,padx=(16,12),pady=(17,0));badge.grid_propagate(False)
        self.text(badge,'',image=icon(kind,20,'accent')).place(relx=.5,rely=.5,anchor='center')
        title=self.text(card,item['title'],14,bold=True,anchor='w',justify='left',wraplength=390)
        title.grid(row=0,column=1,sticky='ew',pady=(16,0))
        pin=Button(card,kind='ghost',symbol='pin',text='',width=30,height=30,fg_color=color('soft') if item['pinned'] else 'transparent',command=lambda:self.pin_id(item['id']))
        pin.grid(row=0,column=2,padx=(6,12),pady=(12,0))
        host=urlsplit(item['target']).hostname if kind=='link' else item['target'].replace('\\','/').split('/')[-1]
        meta='  ·  '.join(x for x in [item['project'],host] if x)
        metadata=self.text(card,meta,11,'muted',anchor='w',wraplength=390)
        metadata.grid(row=1,column=1,columnspan=2,sticky='ew',padx=(0,16),pady=(1,10))
        note=self.text(card,item['note'].replace('\n',' ')[:150],13,'text',anchor='w',justify='left',wraplength=430)
        note.grid(row=2,column=0,columnspan=3,sticky='ew',padx=18,pady=(0,13))
        foot=ctk.CTkFrame(card,fg_color='transparent')
        foot.grid(row=3,column=0,columnspan=3,sticky='ew',padx=18,pady=(0,14))
        date=datetime.fromtimestamp(item['created']).strftime('%d %b')
        self.text(foot,item['position'] or self.t('document' if kind=='file' else 'webPage'),11,'muted',anchor='w').pack(side='left')
        self.text(foot,date,11,'muted').pack(side='right')
        def select(_=None):self.select_item(item['id'],open_detail=True)
        def bindings(widget):
            if widget is pin:return
            widget.bind('<Button-1>',select,add='+')
            for child in widget.winfo_children():
                # CTk's own internal canvas/labels already receive its bound callback.
                if isinstance(child,(ctk.CTkFrame,ctk.CTkLabel)):bindings(child)
        bindings(card)
        def fit(event):
            width=event.width/card._get_widget_scaling()
            title.configure(wraplength=max(160,int(width-110)))
            metadata.configure(wraplength=max(160,int(width-100)))
            note.configure(wraplength=max(200,int(width-40)))
        card.bind('<Configure>',fit,add='+')
        card._canvas.configure(takefocus=1)
        card.bind('<Return>',lambda _:self.select_item(item['id'],open_detail=True))
        card.bind('<FocusIn>',lambda _:card.configure(border_color=color('accent')))
        card.bind('<FocusOut>',lambda _:card.configure(border_color=color('accent') if self.selected_id==item['id'] else color('border')))
        self.cards[item['id']]=card

    def select_item(self,item_id,open_detail=False):
        if item_id not in self.items:return
        self.selected_id=item_id
        for key,card in self.cards.items():
            card.configure(fg_color=color('selected') if key==item_id else color('surface'),border_color=color('accent') if key==item_id else color('border'))
        self.detail()
        if open_detail and self.compact:self.open_inspector()

    def selected(self):return self.items.get(getattr(self,'selected_id',None))

    def pin_id(self,item_id):
        self.store.flag(item_id,'pinned',not self.items[item_id]['pinned'])
        self.render()

    def empty_state(self,filtered):
        frame=ctk.CTkFrame(self.list_scroll,fg_color=color('surface'),corner_radius=12,border_width=1,border_color=color('border'))
        frame.grid(row=0,column=0,sticky='ew',padx=(0,2))
        self.text(frame,'',image=icon('search' if filtered else 'bookmark',40,'accent')).pack(pady=(55,18))
        self.text(frame,self.t('noResults' if filtered else 'empty'),19,bold=True,wraplength=390,justify='center').pack(padx=28)
        self.text(frame,self.t('trySearch' if filtered else 'emptySub'),13,'muted',wraplength=360,justify='center').pack(padx=28,pady=(9,22))
        Button(frame,kind='secondary' if filtered else 'primary',symbol='close' if filtered else 'plus',text=self.t('clearSearch' if filtered else 'new'),command=self.clear_search if filtered else self.edit).pack(pady=(0,55))

    def clear_search(self):
        self.search.set('');self.project_filter='';self.render()

    def detail(self):
        if not hasattr(self,'inspector'):return
        for child in self.inspector.winfo_children():child.destroy()
        self.build_inspector(self.inspector)
        panel=getattr(self,'detail_dialog_container',None)
        if panel is not None and panel.winfo_exists():
            for child in panel.winfo_children():child.destroy()
            self.build_inspector(panel)

    def open_inspector(self):
        if self.dialog and self.dialog.winfo_exists():self.dialog.lift();return
        win=self.dialog=ctk.CTkToplevel(self.root)
        win.title(self.t('details'));win.geometry('420x660');win.minsize(380,540)
        win.configure(fg_color=color('surface'));win.transient(self.root)
        self.root.after(100,lambda:win.grab_set() if win.winfo_exists() else None)
        frame=ctk.CTkFrame(win,fg_color='transparent');frame.pack(fill='both',expand=True)
        self.detail_dialog_container=frame
        self.build_inspector(frame)
        win.bind('<Escape>',lambda _:win.destroy())

    def build_inspector(self,parent):
        item=self.selected()
        self.text(parent,self.t('details'),11,'muted',anchor='w').pack(fill='x',padx=22,pady=(22,16))
        if not item:
            self.text(parent,'',image=icon('bookmark',32,'muted')).pack(pady=(55,14))
            self.text(parent,self.t('selectHint'),14,'muted',wraplength=240,justify='center').pack(padx=20)
            return
        body=ctk.CTkScrollableFrame(parent,fg_color='transparent',scrollbar_button_color=color('border'))
        body.pack(fill='both',expand=True,padx=14,pady=(0,12))
        self.text(body,item['title'],21,bold=True,wraplength=246,justify='left',anchor='w').pack(fill='x',padx=4,pady=(0,9))
        if item['project']:
            chip=ctk.CTkFrame(body,fg_color=color('soft'),corner_radius=5)
            chip.pack(anchor='w',padx=4,pady=(0,20))
            self.text(chip,item['project'],11,'accent',wraplength=220).pack(padx=9,pady=3)
        step=ctk.CTkFrame(body,fg_color=color('selected'),corner_radius=9)
        step.pack(fill='x',padx=4,pady=(0,18))
        self.text(step,self.t('nextStep'),11,'accent',bold=True,anchor='w').pack(fill='x',padx=16,pady=(15,9))
        note=ctk.CTkTextbox(step,height=min(220,max(110,len(item['note'])//3)),fg_color='transparent',text_color=color('text'),font=font(14),wrap='word',border_width=0,activate_scrollbars=True)
        note.insert('1.0',item['note']);note.configure(state='disabled')
        note.pack(fill='x',padx=10,pady=(0,12))
        for title,value,symbol in [('target',item['target'],'link'),('position',item['position'],'bookmark')]:
            if value:
                self.text(body,self.t(title),11,'muted',anchor='w').pack(fill='x',padx=4,pady=(5,3))
                self.text(body,value,12,'text',wraplength=246,justify='left',anchor='w').pack(fill='x',padx=4,pady=(0,12))
        self.action_buttons={}
        for key,symbol,fn in [('resume','arrow',self.resume),('edit','edit',self.edit_selected),('complete','restore' if item['done'] else 'check',self.complete)]:
            text=self.t('restore' if key=='complete' and item['done'] else key)
            b=Button(body,kind='primary' if key=='resume' else 'secondary',symbol=symbol,text=text,height=42,command=fn)
            b.pack(fill='x',padx=4,pady=(0,8));self.action_buttons[key]=b
        if item['done']:
            Button(body,kind='ghost',symbol='trash',text=self.t('delete'),text_color=color('danger'),command=self.delete).pack(fill='x',padx=4,pady=3)
        self.text(body,'Ctrl+N  ·  Ctrl+F',11,'muted',anchor='w').pack(fill='x',padx=4,pady=(17,6))

    def modal(self,title,geometry):
        if self.dialog and self.dialog.winfo_exists():self.dialog.lift();return None
        win=self.dialog=ctk.CTkToplevel(self.root)
        win.title(title);win.geometry(geometry);win.configure(fg_color=color('surface'));win.transient(self.root)
        self.root.after(100,lambda:win.grab_set() if win.winfo_exists() else None)
        win.bind('<Escape>',lambda _:win.destroy())
        return win

    def edit(self,item=None,capture=None):
        win=self.modal(self.t('edit') if item else self.t('new'),'620x720')
        if not win:return
        win.minsize(520,620)
        win.grid_columnconfigure(0,weight=1);win.grid_rowconfigure(1,weight=1)
        head=ctk.CTkFrame(win,fg_color='transparent');head.grid(row=0,column=0,sticky='ew',padx=28,pady=(24,16))
        self.text(head,self.t('edit') if item else self.t('new'),24,bold=True).pack(side='left')
        Button(head,kind='ghost',symbol='close',text='',width=32,height=32,command=win.destroy).pack(side='right')
        content=ctk.CTkScrollableFrame(win,fg_color='transparent',scrollbar_button_color=color('border'))
        content.grid(row=1,column=0,sticky='nsew',padx=22)
        source=item or capture or {};fields={}
        for key in ('title','target','project','position'):
            self.text(content,self.t(key),12,'muted',anchor='w').pack(fill='x',padx=6,pady=(12,6))
            row=ctk.CTkFrame(content,fg_color='transparent');row.pack(fill='x',padx=6)
            if key=='target':Button(row,kind='secondary',symbol='folder',text='',width=42,height=42,command=lambda:self.browse(fields)).pack(side='right',padx=(8,0))
            entry=ctk.CTkEntry(row,height=42,corner_radius=8,border_width=1,border_color=color('border'),fg_color=color('raised'),text_color=color('text'),font=font(13),justify='right' if self.lang=='ar' else 'left')
            entry.insert(0,source.get(key,''));entry.pack(fill='x',expand=True);fields[key]=entry
        self.text(content,self.t('note'),12,'muted',anchor='w').pack(fill='x',padx=6,pady=(16,6))
        self.editor_note=ctk.CTkTextbox(content,height=126,corner_radius=8,border_width=1,border_color=color('border'),fg_color=color('raised'),text_color=color('text'),font=font(14),wrap='word')
        self.editor_note.insert('1.0',source.get('note',''));self.editor_note.pack(fill='x',padx=6,pady=(0,12))
        self.editor_error=self.text(content,'',12,'danger',wraplength=480,justify='left',anchor='w');self.editor_error.pack(fill='x',padx=6)
        foot=ctk.CTkFrame(win,fg_color='transparent');foot.grid(row=2,column=0,sticky='ew',padx=28,pady=(18,24))
        self.text(foot,'Ctrl+Enter',11,'muted').pack(side='left')
        Button(foot,text=self.t('cancel'),kind='ghost',width=100,command=win.destroy).pack(side='right',padx=(8,0))
        def save(_=None):
            data={k:e.get().strip() for k,e in fields.items()};data['note']=self.editor_note.get('1.0','end-1c').strip()
            try:self.store.save(data,item)
            except (ValueError,OSError,sqlite3.Error) as exc:self.editor_error.configure(text=str(exc));return
            win.destroy();self.render();self.status.configure(text=self.t('saved'))
        self.editor_save=Button(foot,kind='primary',symbol='check',text=self.t('save'),width=140,command=save)
        self.editor_save.pack(side='right')
        win.bind('<Control-Return>',save)
        self.root.after(150,lambda:(self.editor_note if capture else fields['title']).focus_set() if win.winfo_exists() else None)
        self.editor_fields=fields
        return fields

    def edit_selected(self):
        item=self.selected()
        if item:
            if self.dialog and self.dialog.winfo_exists():self.dialog.destroy()
            return self.edit(item)

    def settings(self):
        win=self.modal(self.t('settings'),'620x720')
        if not win:return
        win.minsize(520,620)
        self.text(win,self.t('settings'),25,bold=True,anchor='w').pack(fill='x',padx=28,pady=(26,18))
        body=ctk.CTkScrollableFrame(win,fg_color='transparent',scrollbar_button_color=color('border'))
        body.pack(fill='both',expand=True,padx=22)
        self.text(body,self.t('appearance'),12,'muted',anchor='w').pack(fill='x',padx=6,pady=(8,8))
        appearance=ctk.CTkSegmentedButton(body,values=[self.t(k) for k in ('light','dark','system')],command=self.change_theme,height=38,font=font(13),fg_color=color('soft'),selected_color=color('selected'),selected_hover_color=color('selected'),unselected_color=color('soft'),unselected_hover_color=color('selected'),text_color=color('text'))
        appearance.set(self.t(self.appearance));appearance.pack(fill='x',padx=6,pady=(0,22))
        auto=tk.BooleanVar(value=startup_enabled());tray=tk.BooleanVar(value=self.store.setting('close_tray','1')=='1')
        for key,var in [('startup',auto),('closeTray',tray)]:
            ctk.CTkSwitch(body,text=self.t(key),variable=var,font=font(13),text_color=color('text'),progress_color=color('accent'),button_color=color('muted'),button_hover_color=color('text')).pack(fill='x',padx=6,pady=12)
        self.text(body,self.t('shortcutLabel'),12,'muted',anchor='w').pack(fill='x',padx=6,pady=(20,7))
        shortcut=ctk.CTkEntry(body,height=42,font=font(13),fg_color=color('raised'),border_color=color('border'),text_color=color('text'))
        shortcut.insert(0,self.store.setting('hotkey','Ctrl+Alt+B'));shortcut.pack(fill='x',padx=6)
        self.text(body,'Ctrl+Alt+B  /  Ctrl+Shift+B  /  Alt+Shift+B',11,'muted',anchor='w').pack(fill='x',padx=6,pady=(8,24))
        for key,symbol,fn in [('backupNow','download',self.backup_now),('restoreBackup','restore',self.restore_backup),('openData','folder',lambda:os.startfile(self.data_dir))]:
            Button(body,kind='secondary',symbol=symbol,text=self.t(key),anchor='w',command=fn).pack(fill='x',padx=6,pady=5)
        Button(body,kind='ghost',symbol='exit',text=self.t('exit'),anchor='w',command=self.exit).pack(fill='x',padx=6,pady=(18,5))
        self.text(body,f'BackHere {self.version} · Windows {struct.calcsize("P")*8}-bit',11,'muted',anchor='w').pack(fill='x',padx=6,pady=16)
        def apply():
            requested=shortcut.get().strip()
            try:
                parse_hotkey(requested)
                if auto.get()!=startup_enabled():set_startup(auto.get())
                self.store.set_setting('close_tray','1' if tray.get() else '0')
                if self.hotkey and not self.hotkey.rebind(requested):raise OSError(self.t('hotkeyConflict'))
            except (ValueError,OSError) as exc:messagebox.showerror('BackHere',str(exc),parent=win);return
            win.destroy();self.status.configure(text=self.t('saved'))
        Button(win,kind='primary',text=self.t('save'),width=140,command=apply).pack(anchor='e',padx=28,pady=22)
