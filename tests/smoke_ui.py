"""Windows UI integration in a disposable profile. Never alters startup settings."""
import os
import queue
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
with tempfile.TemporaryDirectory() as folder:
    os.environ['LOCALAPPDATA'] = folder
    import tkinter as tk
    from tkinter import ttk
    from backhere import App
    root = tk.Tk()
    app = App(root, testing=True)
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    root.update()
    for code in app.locales['rows']:
        app.lang = code
        app.build()
        root.update()
    app.lang = 'mn'
    app.build()
    fields = app.edit()
    fields['title'].insert(0, 'Монгол — хадгалах туршилт')
    fields['target'].insert(0, 'https://example.com')
    notes = [w for w in app.dialog.winfo_children() if isinstance(w, tk.Text)][0]
    notes.insert('1.0', 'Маргааш 3-р багана шалга')
    frame = [w for w in app.dialog.winfo_children() if isinstance(w, tk.Frame)][0]
    [w for w in frame.winfo_children() if w.cget('text') == app.t('save')][0].invoke()
    root.update()
    assert len(app.store.all()) == 1
    item = app.store.all()[0]
    app.tree.selection_set(item['id'])
    app.detail()
    app.pin()
    assert app.store.all()[0]['pinned'] == 1
    app.complete()
    assert app.store.all()[0]['done'] == 1
    app.set_filter('done')
    app.tree.selection_set(item['id'])
    app.complete()
    assert app.store.all()[0]['done'] == 0
    app.set_filter('active')
    app.search.set('not present')
    app.render()
    assert not app.tree.get_children()
    app.search.set('Монгол')
    app.render()
    assert len(app.tree.get_children()) == 1
    app.settings()
    root.update()
    app.dialog.destroy()
    assert not errors, errors
    # Real Windows tray backend: visibility and clean shutdown, no manual UI input.
    if os.name == 'nt':
        from tray import Tray
        tray = Tray(queue.Queue(), {k: app.t(k) for k in ('show', 'new', 'exit')})
        deadline = time.monotonic() + 5
        while not tray.visible and time.monotonic() < deadline:
            root.update()
            time.sleep(.05)
        assert tray.visible, 'Tray icon did not initialize'
        tray.stop()
    app.exit()
print('12 locales, note save, pin, complete/restore, search, settings and Windows tray passed.')
