"""Desktop UI interaction and layout regression, isolated from real user data."""
from contextlib import ExitStack
import os
import queue
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
with tempfile.TemporaryDirectory() as folder, ExitStack() as cleanup:
    os.environ['LOCALAPPDATA']=folder
    import customtkinter as ctk
    from backhere import App
    root=ctk.CTk()
    app=App(root,testing=True)
    cleanup.callback(app.exit)
    errors=[]
    root.report_callback_exception=lambda *args:errors.append(args)
    root.update()
    assert app.lang=='en','Fresh profile must default to English'
    for code in app.locales['rows']:
        app.lang=code;app.build();root.update()
    app.show_license();root.update();assert app.dialog.title()==app.t('license');app.dialog.destroy()
    # Expired trials keep stored data but block new notes and automatic capture.
    from licensing import TRIAL_SECONDS
    start=app.license.state['start'];app.license.state['start']=time.time()-TRIAL_SECONDS-1
    assert app.edit() is None
    root.update();assert app.dialog.title()==app.t('license');app.dialog.destroy()
    app.capture_session(automatic=True);assert not app.workspace_capture_busy
    app.license.state['start']=start
    app.lang='mn';app.build()
    fields=app.edit()
    fields['title'].insert(0,'Монгол — хадгалах туршилт')
    fields['target'].insert(0,'https://example.com')
    app.editor_note.insert('1.0','Маргааш 3-р багана шалга')
    app.editor_save.invoke();root.update()
    assert len(app.store.all())==1
    item=app.store.all()[0];app.select_item(item['id'])
    app.pin();assert app.store.all()[0]['pinned']==1
    app.complete();assert app.store.all()[0]['done']==1
    app.set_filter('done');app.select_item(item['id']);app.complete()
    assert app.store.all()[0]['done']==0
    app.set_filter('active');app.search.set('not present');app.render()
    assert not app.visible_ids
    app.search.set('Монгол');app.render();assert len(app.visible_ids)==1
    app.settings();root.update();app.dialog.destroy()
    for mode in ('dark','light','system'):
        app.change_theme(mode);root.update()
        assert app.store.setting('appearance')==mode
    root.geometry('980x600');root.update();app.update_layout();root.update();assert app.compact
    assert app.privacy_note.winfo_rooty()+app.privacy_note.winfo_height()<=root.winfo_rooty()+root.winfo_height(), 'Sidebar footer was clipped'
    app.select_item(item['id'],open_detail=True);root.update()
    assert app.detail_dialog_container.winfo_exists()
    app.dialog.destroy()
    # Hosted runners may clamp windows to a 1024px desktop. Exercise both layout
    # branches explicitly, then return to the window's actual logical dimensions.
    app.apply_layout(1240);assert not app.compact
    assert app.inspector.winfo_manager()=='grid'
    app.apply_layout(980);assert app.compact
    root.geometry('1240x790');root.update();app.update_layout()
    assert app.compact==(root.winfo_width()/root._get_window_scaling()<1130)
    from session_model import new_snapshot
    fixture=dict(id='demo-window',title='Research — browser workspace',exe=r'C:\Program Files\Google\Chrome\Application\chrome.exe',app='chrome.exe',target='https://example.com/research',position='',kind='browser',show=1,rect=[100,100,900,700],hwnd=0,pid=0,started=0,unsaved=False,tabs=[dict(url='https://example.com/research',title='Research',active=True,pinned=False)])
    saved_workspace=new_snapshot('Research workspace',[fixture],machine='Demo PC')
    app.store.sessions.save(saved_workspace)
    for code in ('en','mn'):
        app.lang=code;app.show_sessions();root.update()
        assert app.session_selected==saved_workspace['id']
        assert len(app.session_checks)==1
        assert app.session_status.winfo_rooty()+app.session_status.winfo_height() <= app.session_window.winfo_rooty()+app.session_window.winfo_height(), 'Workspace footer clipped'
        app.close_sessions();root.update()
    assert not errors,errors
    # Screenshots use synthetic fixtures in this disposable profile, never real user files.
    if os.environ.get('UI_SCREENSHOTS'):
        from PIL import ImageGrab
        destination=Path(os.environ['UI_SCREENSHOTS']);destination.mkdir(parents=True,exist_ok=True)
        examples=[
            ('Brand launch — visual direction','https://example.com/brand','RAINY Studio','Frame 06','Refine the hero layout. Keep the typography quiet and let the product do the talking.'),
            ('Q4 product roadmap','C:\\Projects\\roadmap.xlsx','Product','Roadmap!C12','Check the release dates in column C, then share the final timeline.'),
            ('Customer research notes','https://example.com/research','Research','Section 3','Compare the three recurring pain points with the interview notes.'),
            ('Voice Studio — next release','https://example.com/voice','RAINY Studio','Milestone 2','Review the new voice samples and confirm the onboarding copy.'),
        ]
        for title,target,project,position,note in examples:
            app.store.save(dict(title=title,target=target,project=project,position=position,note=note))
        app.lang='en';app.search.set('');app.selected_id=None;app.build()
        width=min(1240,max(940,root.winfo_screenwidth()-80));height=min(790,max(560,root.winfo_screenheight()-160))
        root.geometry(f'{width}x{height}+20+35')
        root.update();app.update_layout();root.lift()
        for mode in ('light','dark'):
            app.change_theme(mode);root.update();time.sleep(.15);root.update()
            x,y=root.winfo_rootx(),root.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(destination/f'backhere-{mode}.png')
        if app.compact:
            app.open_inspector();root.update();time.sleep(.2);root.update()
            w=app.dialog;x,y=w.winfo_rootx(),w.winfo_rooty()
            ImageGrab.grab(bbox=(x,y,x+w.winfo_width(),y+w.winfo_height())).save(destination/'backhere-detail.png')
            w.destroy()
        app.lang='mn';app.build();root.update()
        x,y=root.winfo_rootx(),root.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height())).save(destination/'backhere-mongolian.png')
    app.lang='en';app.show_sessions();root.update()
    if os.environ.get('UI_SCREENSHOTS'):
        w=app.session_window;x,y=w.winfo_rootx(),w.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+w.winfo_width(),y+w.winfo_height())).save(destination/'backhere-workspaces.png')
    app.close_sessions();root.update()
    app.lang='en';app.show_license();root.update()
    if os.environ.get('UI_SCREENSHOTS'):
        w=app.dialog;x,y=w.winfo_rootx(),w.winfo_rooty()
        ImageGrab.grab(bbox=(x,y,x+w.winfo_width(),y+w.winfo_height())).save(destination/'backhere-license.png')
    app.dialog.destroy();root.update()
    if os.name=='nt':
        from tray import Tray
        tray=Tray(queue.Queue(),{k:app.t(k) for k in ('show','new','exit')})
        # Run the real Tk dispatcher while native tray/setup threads initialize.
        # update() alone does not mark Tcl as dispatching cross-thread operations.
        import gc
        import faulthandler
        gc.collect()
        deadline=time.monotonic()+10
        def check_tray():
            if tray.ready.is_set() or time.monotonic()>=deadline:
                root.quit()
            else:
                root.after(50,check_tray)
        root.after(50,check_tray)
        root.mainloop()
        if not (tray.ready.is_set() and tray.visible):
            faulthandler.dump_traceback(file=sys.stdout,all_threads=True)
        assert tray.ready.is_set() and tray.visible,('Tray initialization failed',tray.error,tray.thread.is_alive())
        tray.stop()
    app.exit()
print('30 locales, editor save, filters, themes, compact detail drawer, wide layout and tray passed.')
