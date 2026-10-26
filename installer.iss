[Setup]
AppId={{18BD80BA-4C74-4E77-9F9E-580980EB038D}
AppName=BackHere
AppVersion=0.1.0
AppPublisher=Rainy Studio
DefaultDirName={localappdata}\Programs\BackHere
DefaultGroupName=BackHere
PrivilegesRequired=lowest
OutputDir=installer-output
OutputBaseFilename=BackHere-Setup-0.1.0
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\BackHere.exe
WizardStyle=modern
[Files]
Source: "dist\BackHere.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\BackHere"; Filename: "{app}\BackHere.exe"
Name: "{autodesktop}\BackHere"; Filename: "{app}\BackHere.exe"
[Run]
Filename: "{app}\BackHere.exe"; Description: "Launch BackHere"; Flags: nowait postinstall skipifsilent
