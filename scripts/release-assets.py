"""Stage immutable public release files from already tested Windows artifacts."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import hashlib
import shutil
import sys

root=Path(__file__).resolve().parents[1]
module=ast.parse((root/'desktop/backhere.py').read_text('utf-8'))
version=next(node.value.value for node in module.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in node.targets))
artifacts=Path(sys.argv[1]);output=Path(sys.argv[2]);output.mkdir(parents=True,exist_ok=True)
for architecture in ('x64','x86'):
    directory=artifacts/f'BackHere-Windows-{architecture}'
    installer=next(directory.rglob(f'BackHere-Setup-{version}-{architecture}.exe'))
    executable=next(directory.rglob('BackHere.exe'))
    shutil.copyfile(installer,output/installer.name)
    name=f'BackHere-{version}-{architecture}.exe'
    shutil.copyfile(executable,output/name)
    with ZipFile(output/f'BackHere-{version}-{architecture}-portable.zip','w',ZIP_DEFLATED) as archive:
        archive.write(executable,'BackHere.exe')
        archive.writestr('README.txt',f'BackHere {version} / Windows {architecture}\nRun BackHere.exe. No Python required.\nData: %LOCALAPPDATA%\\BackHere\nhttps://github.com/ssboroo/backhere\n')
brand=next((artifacts/'BackHere-Brand-Kit').rglob('*.zip'))
shutil.copyfile(brand,output/brand.name)
for image in (artifacts/'BackHere-UI-x64').rglob('*.png'):
    shutil.copyfile(image,output/image.name)
lines=[hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name for path in sorted(output.iterdir()) if path.is_file() and path.name!='SHA256SUMS.txt']
(output/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n','utf-8')
print(version)
