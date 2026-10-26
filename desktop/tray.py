"""Tray callbacks enqueue events; only Tk's main thread changes the UI."""
import threading


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
        self.thread = threading.Thread(target=self.icon.run, daemon=True)
        self.thread.start()

    @property
    def visible(self):
        return self.icon.visible

    def stop(self):
        self.icon.stop()
