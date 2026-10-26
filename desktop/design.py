"""BackHere design tokens, theme-aware line icons and keyboard-operable controls."""
from functools import lru_cache
import customtkinter as ctk
from PIL import Image, ImageDraw

COLORS = {
    'background': ('#F4F6F5', '#131A17'),
    'sidebar': ('#FBFCFB', '#18211C'),
    'surface': ('#FFFFFF', '#1C2720'),
    'raised': ('#F8FAF8', '#222F26'),
    'text': ('#202D25', '#EDF5EE'),
    'muted': ('#627468', '#A9BAAD'),
    'border': ('#DDE6DF', '#34463A'),
    'accent': ('#326C4B', '#A3DBB4'),
    'on_accent': ('#FFFFFF', '#132C1D'),
    'accent_hover': ('#28593D', '#B7EAC6'),
    'selected': ('#EBF3ED', '#283E2E'),
    'soft': ('#EEF3EF', '#25342A'),
    'danger': ('#A43838', '#F0A0A0'),
}
FONT = 'Segoe UI'


def color(name):
    return COLORS[name]


def resolved(name, dark=False):
    return COLORS[name][int(dark)]


def font(size=13, weight='normal'):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


def _draw_icon(name, ink):
    image = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    def line(points, width=6):
        draw.line(points, fill=ink, width=width, joint='curve')
    def rect(box, radius=4):
        draw.rounded_rectangle(box, radius=radius, outline=ink, width=6)
    if name == 'logo':
        draw.rounded_rectangle((3, 3, 93, 93), radius=25, fill=ink)
        white = '#FFFFFF' if ink == '#326C4B' else '#132C1D'
        draw.arc((25, 24, 73, 73), 35, 300, fill=white, width=8)
        draw.polygon([(18, 29), (43, 24), (27, 48)], fill=white)
    elif name in ('bookmark', 'file'):
        line([(24, 81), (24, 15), (72, 15), (72, 81), (48, 63), (24, 81)]) if name == 'bookmark' else line([(24, 81), (24, 15), (58, 15), (75, 32), (75, 81), (24, 81)])
        if name == 'file':
            line([(57, 16), (57, 34), (74, 34)]); line([(35, 49), (62, 49)]); line([(35, 62), (62, 62)])
    elif name == 'pin':
        line([(33, 14), (68, 14), (64, 40), (76, 56), (23, 56), (36, 40), (33, 14)]); line([(49, 56), (49, 84)])
    elif name == 'check':
        draw.ellipse((13, 13, 83, 83), outline=ink, width=6); line([(29, 48), (43, 62), (68, 34)])
    elif name == 'search':
        draw.ellipse((15, 12, 66, 63), outline=ink, width=6); line([(61, 60), (83, 82)])
    elif name == 'plus':
        line([(48, 18), (48, 78)]); line([(18, 48), (78, 48)])
    elif name in ('arrow', 'external'):
        if name == 'arrow':
            line([(15, 48), (80, 48)]); line([(55, 22), (81, 48), (55, 74)])
        else:
            line([(50, 18), (79, 18), (79, 48)]); line([(79, 18), (41, 56)]); line([(39, 18), (18, 18), (18, 78), (78, 78), (78, 58)])
    elif name == 'folder':
        line([(14, 76), (14, 23), (38, 23), (48, 34), (82, 34), (82, 76), (14, 76)])
    elif name == 'settings':
        draw.ellipse((19, 19, 77, 77), outline=ink, width=6); draw.ellipse((38, 38, 58, 58), outline=ink, width=5)
        for a,b in [((48,8),(48,21)),((48,75),(48,88)),((8,48),(21,48)),((75,48),(88,48)),((18,18),(28,28)),((68,68),(78,78)),((18,78),(28,68)),((68,28),(78,18))]:line([a,b])
    elif name == 'sun':
        draw.ellipse((31, 31, 65, 65), outline=ink, width=6)
        for a,b in [((48,8),(48,21)),((48,75),(48,88)),((8,48),(21,48)),((75,48),(88,48)),((18,18),(27,27)),((69,69),(78,78)),((18,78),(27,69)),((69,27),(78,18))]:line([a,b])
    elif name == 'moon':
        draw.arc((16, 14, 80, 80), 45, 300, fill=ink, width=6); draw.arc((40, 4, 95, 59), 95, 190, fill=ink, width=6)
    elif name == 'link':
        draw.rounded_rectangle((13, 36, 56, 61), radius=12, outline=ink, width=6); draw.rounded_rectangle((41, 36, 84, 61), radius=12, outline=ink, width=6)
    elif name == 'edit':
        line([(20, 62), (65, 17), (79, 31), (34, 76), (17, 79), (20, 62)]); line([(56, 26), (70, 40)])
    elif name == 'trash':
        line([(18, 25), (78, 25)]); line([(34, 25), (34, 14), (62, 14), (62, 25)]); line([(26, 29), (30, 81), (67, 81), (71, 29)]); line([(41, 38), (41, 69)]); line([(56, 38), (56, 69)])
    elif name in ('download', 'upload'):
        line([(18, 59), (18, 80), (79, 80), (79, 59)])
        if name == 'download':line([(48, 13), (48, 62)]);line([(28, 43), (48, 63), (68, 43)])
        else:line([(48, 65), (48, 15)]);line([(28, 34), (48, 14), (68, 34)])
    elif name == 'restore':
        draw.arc((21, 20, 81, 80), 205, 520, fill=ink, width=6);line([(17, 13), (18, 40), (43, 39)])
    elif name == 'shield':
        line([(48,12),(79,25),(76,58),(64,76),(48,85),(32,76),(20,58),(17,25),(48,12)]);line([(32,47),(44,59),(66,36)])
    elif name == 'clock':
        draw.ellipse((13,13,83,83),outline=ink,width=6);line([(48,26),(48,49),(65,58)])
    elif name == 'close':
        line([(23,23),(73,73)]);line([(73,23),(23,73)])
    elif name == 'exit':
        line([(43,17),(19,17),(19,80),(43,80)]);line([(39,48),(83,48)]);line([(66,31),(83,48),(66,65)])
    return image


@lru_cache(maxsize=128)
def icon(name, size=18, role='muted'):
    return ctk.CTkImage(light_image=_draw_icon(name,resolved(role)), dark_image=_draw_icon(name,resolved(role,True)), size=(size,size))


class Button(ctk.CTkButton):
    """Tab/Enter/Space plus a visible keyboard-focus border (CTk 5.2.2 adapter)."""
    def __init__(self, master, *, kind='secondary', symbol=None, **kwargs):
        primary = kind == 'primary'
        ghost = kind == 'ghost'
        options = dict(height=40, corner_radius=9, border_width=0 if primary or ghost else 1,
                       border_color=color('border'), fg_color=color('accent') if primary else ('transparent' if ghost else color('surface')),
                       hover_color=color('accent_hover') if primary else color('soft'),
                       text_color=color('on_accent') if primary else color('text'),
                       text_color_disabled=color('muted'), font=font(13,'bold' if primary else 'normal'))
        if symbol:
            options['image'] = icon(symbol,18,'on_accent' if primary else 'muted')
        options.update(kwargs)
        super().__init__(master, **options)
        self._base_border = options['border_width']
        self._base_border_color = options['border_color']
        self._canvas.configure(takefocus=1)  # pinned CTk adapter; not app-specific code
        self.bind('<Return>', lambda _: self.invoke())
        self.bind('<space>', lambda _: self.invoke())
        self.bind('<FocusIn>', lambda _: self.configure(border_width=2, border_color=color('accent')))
        self.bind('<FocusOut>', lambda _: self.configure(border_width=self._base_border, border_color=self._base_border_color))

    def state(self, states):
        self.configure(state='disabled' if 'disabled' in states else 'normal')
