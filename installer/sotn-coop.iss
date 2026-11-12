; The SOTN Co-op installer (design/M6-playable-build.md). Built by scripts/build_release.sh:
;   ISCC /DVersion=x.y.z /DStage=<staging folder> /DOut=<output folder> sotn-coop.iss
; Per-user, no admin rights, in the folder the player chooses (C:\Games\sotn-coop to start with):
; everything SOTN Co-op has goes in it, the player's data in data\ (D196). An update installs over
; the same folder and replaces only app\ and python\. Holds no game data: the co-op disc is made
; from the player's own disc on first launch.
#ifndef Version
  #define Version "0.0.0"
#endif
; (scripts/test_installer.py installs a copy under another name, beside the player's own)
#ifndef AppId
  #define AppId "SOTN Co-op"
#endif

[Setup]
AppId={#AppId}
AppName=SOTN Co-op
AppVersion={#Version}
AppPublisher=SOTN Co-op contributors
AppPublisherURL=https://github.com/tucker-bower/sotn-coop
; (an update goes to the folder installed to before: UsePreviousAppDir, Inno's default)
DefaultDirName={sd}\Games\sotn-coop
DefaultGroupName={#AppId}
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
; The folder page every time, filled in with the folder it's in now: another folder moves it there
; (issue 249). The launcher's own updates run silently, into the same folder.
DisableDirPage=no
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
; (/NOLAUNCH=1: tests, so nothing opens on the screen)
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\app\launcher\app.py"""; WorkingDir: "{app}"; Flags: nowait skipifnotsilent; Check: Launch

[UninstallDelete]
; What running it made inside the program folder (Python's caches). The player's data\ stays,
; unless they say otherwise (below).
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\python"

[Code]
function Launch: Boolean;
begin
  Result := ExpandConstant('{param:NOLAUNCH|0}') <> '1';
end;

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

// Installed to another folder than before (issue 249): the player's data\ moves to the new one,
// copied first and deleted only once the copy is whole, and the old program goes.
function MoveFrom(Old, New: String): Boolean;
var
  Code: Integer;
begin
  Result := True;
  if not DirExists(Old + '\data') or DirExists(New + '\data') then
    exit;
  WizardForm.StatusLabel.Caption := 'Moving your castles, saves and discs to ' + New + '...';
  // robocopy: 0-7 is success (8 and up: something wasn't copied)
  if not Exec(ExpandConstant('{sys}\robocopy.exe'), '"' + Old + '\data" "' + New + '\data" /E /R:1 /W:1 /NP /NFL /NDL /NJH /NJS',
              '', SW_HIDE, ewWaitUntilTerminated, Code) or (Code >= 8) then
  begin
    Result := False;
    exit;
  end;
  DelTree(Old + '\data', True, True, True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Old, New: String;
begin
  if CurStep <> ssPostInstall then
    exit;
  Old := RemoveBackslashUnlessRoot(WizardForm.PrevAppDir);
  New := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
  if (Old = '') or (CompareText(Old, New) = 0) or not DirExists(Old) then
    exit;
  if not MoveFrom(Old, New) then
  begin
    if not WizardSilent then
      MsgBox('Your castles, saves and discs couldn''t all be copied to ' + New + '. They''re still in ' + Old +
             '\data: copy that folder into ' + New + ' yourself.', mbError, MB_OK);
    exit;
  end;
  DelTree(Old + '\app', True, True, True);
  DelTree(Old + '\python', True, True, True);
  DeleteFile(Old + '\SOTN Co-op.lnk');
  DeleteFile(Old + '\unins000.exe');
  DeleteFile(Old + '\unins000.dat');
  RemoveDir(Old);
end;

// Uninstalling asks before deleting the player's castles, saves and discs (data\): No is the default.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and DirExists(ExpandConstant('{app}\data')) and not UninstallSilent then
    if MsgBox('Also delete your castles, saves and discs?' + #13#10 + '(They''re in ' + ExpandConstant('{app}\data') + ')',
              mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{app}'), True, True, True);
end;
