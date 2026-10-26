"""Tray callbacks enqueue events; only Tk's main thread changes the UI."""
import threading
import logging


class Tray:
    def __init__(self, events, labels):
        import pystray
        from PIL import Image, ImageDraw
        image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 62, 62), radius=16, fill='#486342')
        draw.arc((16, 17, 48, 49), 40, 300, fill='white', width=5)
        draw.polygon([(12, 18), (28, 17), (17, 31)], fill='white')
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
