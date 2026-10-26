"""Deterministic checks for the theme's actual foreground/background pairs."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from design import COLORS


def luminance(hex_value):
    channels=[int(hex_value[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in channels]
    return sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))


class ThemeTests(unittest.TestCase):
    def test_body_caption_and_primary_button_contrast(self):
        for mode in (0,1):
            for foreground,background in [('text','background'),('text','surface'),('muted','background'),('muted','surface'),('text','selected'),('on_accent','accent')]:
                values=sorted([luminance(COLORS[foreground][mode]),luminance(COLORS[background][mode])])
                self.assertGreaterEqual((values[1]+.05)/(values[0]+.05),4.5,(mode,foreground,background))
