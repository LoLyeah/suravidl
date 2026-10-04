; inno setup 6 script for suravidl per-user installation

#ifndef AppVersion
  #error AppVersion must be defined via /DAppVersion=x.y.z on the ISCC command line
#endif

; compile-time absolute paths: SourcePath is where this script sits, so the
; caller's working directory and ISPP's relative-path rules both stop mattering
#define RepoRoot AddBackslash(AddBackslash(SourcePath) + "..\..")
#define ScriptDir AddBackslash(SourcePath)

[Setup]
; stable guid chosen once for suravidl per-user installations
AppId={{E8F67C29-7B1A-4D3E-9A52-3E6B20261004}}
AppName=suravidl
AppVersion={#AppVersion}
; per-user installation into user profile without requiring administrator elevation
PrivilegesRequired=lowest
; no PrivilegesRequiredOverridesAllowed directive on purpose: absent, it means no
; override at all, so users are never offered a mode that asks for admin rights
DefaultDirName={localappdata}\Programs\suravidl
; disable start menu group page because modern windows apps use a direct shortcut
DisableProgramGroupPage=yes
; skip destination directory selection on upgrade to avoid redundant questions
DisableDirPage=auto
SourceDir={#RepoRoot}
; lands next to the script: packaging/windows/Output/suravidl-setup.exe
OutputDir={#ScriptDir}Output
OutputBaseFilename=suravidl-setup
SetupIconFile={#RepoRoot}assets\icon.ico
UninstallDisplayIcon={app}\suravidl.exe
LicenseFile={#RepoRoot}LICENSE
; request running instances to close during upgrades so files can be replaced
CloseApplications=yes
; the application controls its own relaunch; prevent restart manager double-launch
RestartApplications=no
SolidCompression=yes
Compression=lzma2
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; desktop icon is opt-in to avoid cluttering the desktop; start menu is standard
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\suravidl.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; start menu shortcut in user programs folder ({userprograms}\suravidl.lnk)
Name: "{userprograms}\suravidl"; Filename: "{app}\suravidl.exe"
; optional desktop shortcut created only if selected in tasks
Name: "{userdesktop}\suravidl"; Filename: "{app}\suravidl.exe"; Tasks: desktopicon

[Run]
; launch prompt after interactive install only; silent upgrades are relaunched by the app itself
Filename: "{app}\suravidl.exe"; Description: "Launch suravidl"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; the engine stages update downloads under its cache home
; (%USERPROFILE%\.cache\suravidl\updates on Windows) and nothing else
; cleans a failed apply; on uninstall that subtree goes with the app.
; user data lives in %USERPROFILE%\.suravidl (jobs.db, settings, cookies)
; and is never touched, so it survives uninstall and reinstall.
; the user-profile root has no named Inno constant - only the env-var
; form expands here; an unknown constant aborts the compile, loudly
Type: filesandordirs; Name: "{%USERPROFILE}\.cache\suravidl\updates"
