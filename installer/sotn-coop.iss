; The SOTN Co-op installer (design/M6-playable-build.md). Built by scripts/build_release.sh:
;   ISCC /DVersion=x.y.z /DStage=<staging folder> /DOut=<output folder> sotn-coop.iss
; Per-user, no admin rights, in the folder the player chooses (C:\Games\sotn-coop to start with):
; everything SOTN Co-op has goes in it, the player's data in data\ (D196). An update installs over
; the same folder and replaces only app\ and python\. Holds no game data: the co-op disc is made
; from the player's own disc on first launch.
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppName=SOTN Co-op
AppVersion={#Version}
AppPublisher=SOTN Co-op contributors
AppPublisherURL=https://github.com/tucker-bower/sotn-coop
; (an update goes to the folder installed to before: UsePreviousAppDir, Inno's default)
DefaultDirName={sd}\Games\sotn-coop
DefaultGroupName=SOTN Co-op
PrivilegesRequired=lowest
OutputDir={#Out}
OutputBaseFilename=SOTN-Coop-setup-{#Version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayName=SOTN Co-op
UninstallDisplayIcon={app}\app\launcher\assets\icon.ico
SetupIconFile={#Stage}\app\launcher\assets\icon.ico
InfoBeforeFile={#Stage}\app\LICENSES\README.txt
; As few pages as possible (design/M7b-polish.md): what this is, where, a desktop shortcut, done.
; The folder page only on a first install.
DisableDirPage=auto
DisableReadyPage=yes

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{app}\SOTN Co-op"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app\launcher\assets\icon.ico"
Name: "{group}\SOTN Co-op"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app\launcher\assets\icon.ico"
Name: "{userdesktop}\SOTN Co-op"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; IconFilename: "{app}\app\launcher\assets\icon.ico"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "A desktop shortcut"; GroupDescription: "Shortcuts:"

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; Description: "Start SOTN Co-op"; Flags: postinstall nowait skipifsilent
; An update the launcher started (silent): the launcher starts again when it's done
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; Flags: nowait skipifnotsilent

[UninstallDelete]
; What running it made inside the program folder (Python's caches). The player's data\ stays,
; unless they say otherwise (below).
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\python"

[Code]
// The folder must be one the player can write to: no admin rights are asked for.
function NextButtonClick(CurPageID: Integer): Boolean;
var
  Probe: String;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    Probe := AddBackslash(WizardDirValue) + '.sotn-coop-write-test';
    if not (ForceDirectories(WizardDirValue) and SaveStringToFile(Probe, 'ok', False)) then
    begin
      MsgBox('SOTN Co-op can''t write to ' + WizardDirValue + '. Choose a folder of your own, like C:\Games.', mbError, MB_OK);
      Result := False;
    end
    else
      DeleteFile(Probe);
  end;
end;

// Uninstalling asks before deleting the player's castles, saves and discs (data\): No is the default.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DirExists(ExpandConstant('{app}\data')) and not UninstallSilent then
    if MsgBox('Also delete your castles, saves and discs?' + #13#10 + '(They''re in ' + ExpandConstant('{app}\data') + ')',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{app}'), True, True, True);
end;
