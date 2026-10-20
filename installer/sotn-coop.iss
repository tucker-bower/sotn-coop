; The SOTN Co-op installer (design/M6-playable-build.md). Built by scripts/build_release.sh:
;   ISCC /DVersion=x.y.z /DStage=<staging folder> /DOut=<output folder> sotn-coop.iss
; Per-user, no admin rights: %LOCALAPPDATA%\Programs\SOTN Co-op. Holds no game data: the
; co-op disc is made from the player's own disc on first launch.
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppName=SOTN Co-op
AppVersion={#Version}
AppPublisher=SOTN Co-op contributors
AppPublisherURL=https://github.com/tucker-bower/sotn-decomp-coop
DefaultDirName={localappdata}\Programs\SOTN Co-op
DefaultGroupName=SOTN Co-op
PrivilegesRequired=lowest
OutputDir={#Out}
OutputBaseFilename=SOTN-Coop-setup-{#Version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName=SOTN Co-op
LicenseFile={#Stage}\app\LICENSES\README.txt

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\SOTN Co-op"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"
Name: "{userdesktop}\SOTN Co-op"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "A desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; Description: "Start SOTN Co-op"; Flags: postinstall nowait skipifsilent
