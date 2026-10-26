from pathlib import Path
from PIL import Image, ImageDraw
output = Path('build-resources')
output.mkdir(exist_ok=True)
image = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((8, 8, 248, 248), radius=64, fill='#486342')
draw.arc((64, 68, 192, 196), 40, 300, fill='white', width=20)
draw.polygon([(48, 72), (112, 68), (68, 124)], fill='white')
image.save(output / 'backhere.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
