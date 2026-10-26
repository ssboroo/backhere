from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'desktop'))
from brand import draw_brand
output=root/'build-resources'
output.mkdir(exist_ok=True)
image=draw_brand(1024)
image.save(output/'backhere.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
image.save(output/'backhere-mark.png')
draw_brand(1024,'#A3DBB4','#132C1D').save(output/'backhere-mark-dark.png')
with ZipFile(output/'BackHere-Brand-Kit-0.5.0.zip','w',ZIP_DEFLATED) as archive:
    for source in sorted((root/'brand').iterdir()):
        if source.is_file():archive.write(source,source.name)
    for source in output.glob('*.png'):archive.write(source,source.name)
    archive.write(output/'backhere.ico','backhere.ico')
