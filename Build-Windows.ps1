param([ValidateSet('x64','x86')][string]$Architecture='x64')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$selector = if ($Architecture -eq 'x86') { '-3.12-32' } else { '-3.12-64' }
$environment = '.venv-' + $Architecture
& py $selector -m venv $environment
if ($LASTEXITCODE -ne 0) { throw "Install Python 3.12 $Architecture from python.org" }
$python = Join-Path $environment 'Scripts\python.exe'
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $python tests\smoke_ui.py
if ($LASTEXITCODE -ne 0) { throw 'UI tests failed' }
& $python scripts\make-icon.py
if ($LASTEXITCODE -ne 0) { throw 'Icon generation failed' }
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name BackHere --icon build-resources/backhere.ico --add-data 'desktop/locales.json;.' --add-data 'build-resources/backhere.ico;.' --hidden-import pystray._win32 desktop/backhere.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Write-Host "Built $Architecture dist\BackHere.exe"
