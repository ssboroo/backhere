#ifndef TargetArch
#define TargetArch "x64"
#endif
#define AppVersion "0.5.1"
[Setup]
AppId={{18BD80BA-4C74-4E77-9F9E-580980EB038D}
AppName=BackHere
AppVersion={#AppVersion}
AppPublisher=Rainy Studio
DefaultDirName={localappdata}\Programs\BackHere
DefaultGroupName=BackHere
PrivilegesRequired=lowest
MinVersion=10.0
AppMutex=Local\BackHere.Desktop.v1
#if TargetArch == "x64"
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#endif
OutputDir=installer-output
OutputBaseFilename=BackHere-Setup-{#AppVersion}-{#TargetArch}
SetupIconFile=build-resources\backhere.ico
UninstallDisplayIcon={app}\BackHere.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
[Files]
Source: "dist\BackHere.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\BackHere"; Filename: "{app}\BackHere.exe"
Name: "{autodesktop}\BackHere"; Filename: "{app}\BackHere.exe"
[Run]
Filename: "{app}\BackHere.exe"; Description: "Launch BackHere"; Flags: nowait postinstall skipifsilent
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "BackHere"; Flags: uninsdeletevalue dontcreatekey
