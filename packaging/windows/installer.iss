; Inno Setup script for Hacker Cam. Built by packaging/build_windows.ps1:
;   iscc /DAppVersion=1.0.0 packaging\windows\installer.iss
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Hacker Cam"
#define AppExe "HackerCam.exe"

[Setup]
AppId={{7C1E2B9A-4F3D-4E8A-9B61-2D5A8C3F0E17}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Hacker Cam
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=HackerCam-{#AppVersion}-windows-x64-setup
SetupIconFile=..\icons\hacker_cam.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startup"; Description: "Start Hacker Cam when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\..\dist\HackerCam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Messages]
FinishedLabel=Hacker Cam is installed.%n%nIt runs in the system tray (the >_ icon). You also need OBS Studio 30+ installed: open it once and click "Start Virtual Camera", then select "OBS Virtual Camera" in Zoom/Teams/Meet.
