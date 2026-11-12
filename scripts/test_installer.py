"""Manual: the installer moves a player's data to a new folder (issue 249). Windows only (WSL).

Builds a tiny installer from installer/sotn-coop.iss under another AppId ("SOTN Co-op Test"), so the
player's own install, its Start menu folder and its uninstall entry are never touched. Installs it
to folder A, puts a castle in A\\data, installs again to folder B, and checks the castle is in
B\\data and A is gone; then uninstalls it.

    python3 scripts/test_installer.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def win(p):
    return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True, check=True).stdout.strip()


def iscc():
    """Inno Setup's compiler, in the emulators folder (env.toml, as scripts/build_release.sh finds it)."""
    sys.path.insert(0, str(ROOT / "harness"))
    from coop_env import ENV, path
    return Path(path(ENV["paths"]["win_emulators"])) / "InnoSetup" / "ISCC.exe"


def windows_temp():
    t = subprocess.run(["cmd.exe", "/c", "echo %TEMP%"], capture_output=True, text=True, cwd="/mnt/c").stdout.strip()
    return Path(subprocess.run(["wslpath", "-u", t], capture_output=True, text=True, check=True).stdout.strip()) / "sotn-coop-installer-test"


def main():
    global TEMP
    TEMP = windows_temp()
    if TEMP.exists():
        shutil.rmtree(TEMP)
    stage, out, a, b = TEMP / "stage", TEMP / "out", TEMP / "A" / "sotn-coop", TEMP / "B" / "sotn-coop"
    (stage / "app/launcher/assets").mkdir(parents=True)
    (stage / "app/LICENSES").mkdir(parents=True)
    shutil.copy(ROOT / "launcher/assets/icon.ico", stage / "app/launcher/assets/icon.ico")
    (stage / "app/LICENSES/README.txt").write_text("test")
    (stage / "app/version.txt").write_text("test")
    out.mkdir()
    shutil.copy(ROOT / "installer/sotn-coop.iss", TEMP / "sotn-coop.iss")
    subprocess.run([str(iscc()), "/Q", "/DVersion=0.0.1", "/DAppId=SOTN Co-op Test", f"/DStage={win(stage)}",
                    f"/DOut={win(out)}", "sotn-coop.iss"], cwd=TEMP, check=True, stdin=subprocess.DEVNULL)
    setup = out / "SOTN-Coop-setup-0.0.1.exe"
    quiet = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NOLAUNCH=1", "/MERGETASKS=!desktopicon"]
    failures = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    try:
        subprocess.run([str(setup), *quiet, f"/DIR={win(a)}"], check=True)
        check((a / "app/version.txt").exists(), "installed to folder A")
        (a / "data/castles/Tucker").mkdir(parents=True)
        (a / "data/castles/Tucker/castle.json").write_text('{"name": "Tucker"}')
        (a / "data/settings.json").write_text("{}")
        subprocess.run([str(setup), *quiet, f"/DIR={win(a)}"], check=True)
        check((a / "data/castles/Tucker/castle.json").exists(), "installed again to A: the data stays")
        subprocess.run([str(setup), *quiet, f"/DIR={win(b)}"], check=True)
        check((b / "data/castles/Tucker/castle.json").read_text() == '{"name": "Tucker"}' and (b / "data/settings.json").exists(),
              "installed to folder B: the castle and settings moved there")
        check((b / "app/version.txt").exists() and (b / "unins000.exe").exists(), "the program is in B, with its uninstaller")
        check(not a.exists(), "folder A is gone")
    finally:
        if (b / "unins000.exe").exists():
            subprocess.run([str(b / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES"])
        elif (a / "unins000.exe").exists():
            subprocess.run([str(a / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES"])
        shutil.rmtree(TEMP, ignore_errors=True)
    print("all passed" if not failures else f"{len(failures)} FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
