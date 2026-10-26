"""Tray callbacks enqueue events; only Tk's main thread changes the UI."""
import threading
import logging


class Tray:
    def __init__(self, events, labels):
        import pystray
        from brand import draw_brand
        image = draw_brand(64)
        self.icon = pystray.Icon('BackHere', image, 'BackHere', pystray.Menu(
            pystray.MenuItem(labels['show'], lambda *_: events.put(('show', None)), default=True),
            pystray.MenuItem(labels['new'], lambda *_: events.put(('new', None))),
            pystray.MenuItem(labels['exit'], lambda *_: events.put(('exit', None)))
        ))
        self.ready = threading.Event()
        self.error = None
        self.events = events
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def setup(self, icon):
        try:
            icon.visible = True
        except Exception as exc:
            self.error = str(exc)
            logging.exception('Tray setup failed')
            self.events.put(('tray_error', self.error))
        finally:
            self.ready.set()

    def run(self):
        try:
            self.icon.run(setup=self.setup)
        except Exception as exc:
            self.error = str(exc)
            logging.exception('Tray loop failed')
            self.ready.set()
            self.events.put(('tray_error', self.error))

    @property
    def visible(self):
        return self.icon.visible

    def stop(self):
        self.icon.stop()
