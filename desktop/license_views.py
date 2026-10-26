"""License status stays accessible after expiry; user data is never deleted."""
import math
from tkinter import messagebox
import customtkinter as ctk
from design import Button,color,font

class LicenseView:
    def license_summary(self):
        state=self.license.status(persist=False)
        if state['kind']=='trial':return self.t('trial')+f' · {math.ceil(state["remaining"]/3600)} h'
        return self.t(state['kind'])
    def require_license(self,quiet=False):
        if self.license.allowed():return True
        if not quiet:
            if self.dialog and self.dialog.winfo_exists():
                # Never destroy an editor with unsaved text when the trial ends.
                messagebox.showinfo(self.t('license'),self.license_summary()+'\n'+self.t('trialInfo'),parent=self.dialog)
            else:self.show_license()
        return False
    def license_tick(self):
        if self.closing:return
        if self.license.status()['kind'] not in ('trial','licensed'):self.workspace_cancel.set()
        if getattr(self,'license_button',None) and self.license_button.winfo_exists():self.license_button.configure(text=self.license_summary())
        self.root.after(60000,self.license_tick)
    def show_license(self):
        win=self.modal(self.t('license'),'650x570')
        if not win:return
        scale=win._get_window_scaling()
        width=min(650,int(win.winfo_screenwidth()/scale)-60)
        height=min(570,int(win.winfo_screenheight()/scale)-100)
        win.minsize(min(520,width),min(430,height));win.geometry(f'{width}x{height}+30+30')
        self.text(win,self.t('license'),25,bold=True).pack(anchor='w',padx=26,pady=(24,8))
        body=ctk.CTkScrollableFrame(win,fg_color='transparent');body.pack(fill='both',expand=True,padx=20,pady=10)
        self.text(body,self.license_summary(),17,'accent',bold=True,anchor='w').pack(fill='x',padx=6,pady=8)
        self.text(body,self.t('trialInfo'),12,'muted',wraplength=540,justify='left',anchor='w').pack(fill='x',padx=6,pady=8)
        self.text(body,self.t('deviceId'),12,'muted',anchor='w').pack(fill='x',padx=6,pady=(14,6))
        device=ctk.CTkEntry(body,font=font(12),height=38);device.insert(0,self.license.device);device.configure(state='readonly');device.pack(fill='x',padx=6)
        def copy():self.root.clipboard_clear();self.root.clipboard_append(self.license.device)
        Button(body,kind='ghost',text=self.t('copyDevice'),command=copy).pack(anchor='w',padx=6,pady=5)
        self.text(body,self.t('licenseKey'),12,'muted',anchor='w').pack(fill='x',padx=6,pady=(14,6))
        entry=ctk.CTkTextbox(body,height=100,font=font(12),wrap='char');entry.pack(fill='x',padx=6)
        error=self.text(body,'',12,'danger',wraplength=540,anchor='w');error.pack(fill='x',padx=6,pady=8)
        def activate():
            try:self.license.activate(entry.get('1.0','end-1c').strip())
            except (OSError,ValueError):error.configure(text=self.t('licenseInvalid'));return
            win.destroy();self.license_button.configure(text=self.license_summary());messagebox.showinfo('BackHere',self.t('licensed'),parent=self.root)
        Button(body,kind='primary',text=self.t('activateLicense'),command=activate).pack(anchor='e',padx=6,pady=8)
