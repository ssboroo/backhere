"""Windows CI smoke test. Uses an isolated temporary application data directory."""
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
with tempfile.TemporaryDirectory() as folder:
    os.environ['LOCALAPPDATA'] = folder
    import tkinter as tk
    from backhere import App
    root = tk.Tk()
    app = App(root)
    root.update()
    for code in app.locales['rows']:
        app.lang = code
        app.build()
        root.update()
    app.lang = 'mn'
    app.build()
    fields = app.edit()
    root.update()
    assert fields is not None
    app.dialog.destroy()
    app.exit()
print('Desktop UI initialized, 12 languages rendered, editor opened and closed.')
