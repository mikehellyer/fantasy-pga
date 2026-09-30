; Inno Setup script for the Windows installer.
; Built by tools/build.py:  iscc /DAppVersion=x.y.z packaging\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{C4A81E29-6B3F-4D07-8E5A-2F9D1B7C6A43}
AppName=Fantasy PGA
AppVersion={#AppVersion}
AppPublisher=Mike Hellyer
AppPublisherURL=https://github.com/mikehellyer/fantasy-pga
DefaultDirName={autopf}\Fantasy PGA
DefaultGroupName=Fantasy PGA
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Fantasy-PGA-{#AppVersion}-Windows-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\Fantasy PGA.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequiredOverridesAllowed=dialog

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\Fantasy PGA\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\Fantasy PGA"; Filename: "{app}\Fantasy PGA.exe"
Name: "{group}\Uninstall Fantasy PGA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Fantasy PGA"; Filename: "{app}\Fantasy PGA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Fantasy PGA.exe"; Description: "{cm:LaunchProgram,Fantasy PGA}"; Flags: nowait postinstall skipifsilent
