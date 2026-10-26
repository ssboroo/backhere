"""BackHere's source-of-truth vector-friendly bookmark/return mark."""
from PIL import Image, ImageDraw


def draw_brand(size=128, tile='#326C4B', ink='#FFFFFF'):
    scale=4
    image=Image.new('RGBA',(128*scale,128*scale),(0,0,0,0))
    draw=ImageDraw.Draw(image)
    def box(values):return tuple(int(v*scale) for v in values)
    def points(values):return [(int(x*scale),int(y*scale)) for x,y in values]
    draw.rounded_rectangle(box((2,2,126,126)),radius=30*scale,fill=tile)
    draw.polygon(points([(36,23),(76,23),(94,41),(94,106),(65,90),(36,106)]),fill=ink)
    # The folded corner and returning arrow are one distinct, legible silhouette.
    draw.polygon(points([(76,23),(76,42),(94,42)]),fill=tile)
    draw.arc(box((47,45,83,81)),90,270,fill=tile,width=8*scale)
    draw.line(points([(65,45),(52,45)]),fill=tile,width=8*scale)
    draw.polygon(points([(48,45),(60,34),(60,56)]),fill=tile)
    draw.line(points([(65,81),(79,81)]),fill=tile,width=8*scale)
    return image.resize((size,size),Image.Resampling.LANCZOS)
