; Inno Setup script for plumpick. Build with: uv run python scripts/build_installer.py
; (it passes /DAppVersion=... from pyproject.toml and builds dist/plumpick first if missing).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "plumpick"
#define AppExe "plumpick.exe"
#define Publisher "hiddenhari"

[Setup]
; Never change AppId: Windows uses it to recognise upgrades and to find the uninstaller.
AppId={{D78F6534-A1C3-4402-8215-2648E12DC681}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
VersionInfoVersion={#AppVersion}
; Per-user install by default (no admin prompt, lands in %LOCALAPPDATA%\Programs);
; the wizard offers "install for all users" for those who want it.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\src\plumpick\assets\plumpick.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=plumpick-setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Shell needs to refresh because of the "Open with" registration below.
ChangesAssociations=yes
; Close a running plumpick before replacing its files (upgrade/uninstall) and restart it after.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "foldermenu"; Description: "Add ""Open with plumpick"" to the folder right-click menu"; GroupDescription: "Explorer integration:"

[Files]
Source: "..\dist\plumpick\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; "Open with" list for the image types plumpick handles. Registered under
; Applications\ (not as the default handler), so existing associations are untouched.
; uninsdeletekey removes the whole key again on uninstall.
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#AppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".jpg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".jpeg"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".png"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".webp"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".bmp"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".gif"; ValueData: ""
; Folder right-click entry (optional task).
Root: HKA; Subkey: "Software\Classes\Directory\shell\plumpick"; ValueType: string; ValueData: "Open with {#AppName}"; Flags: uninsdeletekey; Tasks: foldermenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\plumpick"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExe}"""; Tasks: foldermenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\plumpick\command"; ValueType: string; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: foldermenu

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Anything created inside the install folder after install (e.g. __pycache__) so the folder goes away completely.
; The .plumpick.json files in users' image folders are their data and are left alone.
Type: filesandordirs; Name: "{app}"
