; Inno Setup Script for WAC Huawei LLDP Crawl Data
; Packages the PyInstaller --onedir output into a Windows installer

#define MyAppName "WAC Huawei LLDP Crawl Data"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "mriazh"
#define MyAppExeName "WAC-Crawl.exe"

[Setup]
AppId={{B8F3A2D1-7C4E-4A9B-8D6F-1E2C3B4A5D6E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\WAC-Crawl
DefaultGroupName={#MyAppName}
OutputBaseFilename=WAC-Crawl-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
OutputDir=..\output

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\WAC-Crawl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only delete application files in the install directory.
; Do NOT delete %APPDATA%/WAC-Crawl/ to preserve user config (config.json).
Type: filesandordirs; Name: "{app}"
