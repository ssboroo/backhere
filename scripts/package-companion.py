from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
root=Path(__file__).resolve().parents[1]
output=root/'build-resources/BackHere-Browser-Companion-0.6.0.zip'
output.parent.mkdir(exist_ok=True)
with ZipFile(output,'w',ZIP_DEFLATED) as archive:
 for path in sorted((root/'browser-companion').iterdir()):
  if path.is_file():archive.write(path,path.name)
