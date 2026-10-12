; Inno Setup script: wraps the PyInstaller onedir build into a per-user installer.
; Build:  iscc /DAppVersion=1.7.0 packaging\windows\installer.iss   (run from the repository root)

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "RPG Database Manager"
#define AppExe "RPG_Database_Manager.exe"

[Setup]
AppId={{6B0F3A52-3E0C-4D8E-9C55-7A1D0C2E9B41}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=RPG Database Manager Team
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Installs for the current user only: no administrator prompt
PrivilegesRequired=lowest
OutputDir=..\..\installer-output
OutputBaseFilename=RPG_Database_Manager-Setup-x64
SetupIconFile=..\..\data\icons\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/normal
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\RPG_Database_Manager\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

; Your campaigns (Documents\RPG Database Manager) are deliberately NOT removed on uninstall.
