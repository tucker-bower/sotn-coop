"""A real Android device over USB (design/M9: Tucker's playtest on his AYN Thor).

    python android/device.py install [apk]   the newest .env/android/*.apk onto the device
    python android/device.py disc            the retail disc into Download/SOTN on the device,
                                             ready for the app's "Choose my disc's folder"
    python android/device.py log [file]      the app's log since it started (default
                                             .env/out/device-log.txt), for a playtest's bugs

The device needs USB debugging on (Settings > About > tap Build number 7 times, then
Developer options > USB debugging), and to allow this PC when it asks. From WSL, the Windows
adb (Emulators\\android-tools) talks to the device: WSL can't see USB devices itself.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
PKG = "org.sotncoop.app"
CUE = "Castlevania - Symphony of the Night (USA).cue"
BINS = ["Castlevania - Symphony of the Night (USA) (Track 1).bin",
        "Castlevania - Symphony of the Night (USA) (Track 2).bin"]


def adb_path():
    """Windows' adb under WSL (USB devices are Windows'), else the one on PATH."""
    if "microsoft" in os.uname().release.lower():
        from coop_env import ENV, path
        win = path(ENV["paths"]["win_emulators"]) / "android-tools" / "platform-tools" / "adb.exe"
        if win.exists():
            return str(win)
    return shutil.which("adb") or str(Path.home() / "android" / "platform-tools" / "adb")


def windows_path(p):
    """A WSL path as the Windows adb wants it."""
    if "microsoft" in os.uname().release.lower():
        return subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True, check=True).stdout.strip()
    return str(p)


# Its own adb server port: from WSL, the Windows adb on the default port reaches the Linux adb
# server (WSL forwards localhost), which can't see USB devices
PORT = ["-P", "5038"]


def adb(*args, **kw):
    return subprocess.run([adb_path(), *PORT, "-d", *args], text=True, **kw)


def device():
    out = subprocess.run([adb_path(), *PORT, "devices", "-l"], capture_output=True, text=True).stdout
    usb = [line for line in out.splitlines()[1:] if line.strip() and "emulator-" not in line]
    if not usb:
        raise SystemExit("No device: plug it in with USB debugging on (see python android/device.py --help).")
    if "unauthorized" in usb[0]:
        raise SystemExit("The device hasn't allowed this PC yet: tap Allow on its screen, then try again.")
    return usb[0]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--help"
    if cmd not in ("install", "disc", "log"):
        print(__doc__)
        return 0
    print("device:", device())
    if cmd == "install":
        apk = Path(sys.argv[2]) if len(sys.argv) > 2 else max((ROOT / ".env" / "android").glob("*.apk"), key=os.path.getmtime)
        print("installing", apk.name)
        # -r keeps the app's data (the disc, saves); a different signing key needs an uninstall first
        r = adb("install", "-r", windows_path(apk), capture_output=True)
        print((r.stdout + r.stderr).strip())
        return r.returncode
    if cmd == "disc":
        folder = "/sdcard/Download/SOTN"
        adb("shell", "mkdir", "-p", folder, check=True)
        cue = ROOT / ".env" / "out" / CUE
        cue.write_text("\n".join([f'FILE "{BINS[0]}" BINARY', "  TRACK 01 MODE2/2352", "    INDEX 01 00:00:00",
                                  f'FILE "{BINS[1]}" BINARY', "  TRACK 02 AUDIO", "    INDEX 00 00:00:00",
                                  "    INDEX 01 00:02:00"]) + "\n")
        from coop_env import DISKS
        for f in [cue] + [DISKS / b for b in BINS]:
            print("copying", f.name)
            adb("push", windows_path(f), f"{folder}/{f.name}", check=True)
        print("Done: in the app, Choose my disc's folder > Download > SOTN > Use this folder > Allow.")
        return 0
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / ".env" / "out" / "device-log.txt"
    log = adb("logcat", "-d", "-s", "python:*", "SDL:*", "AndroidRuntime:*", "DEBUG:*",
              capture_output=True).stdout
    out.write_text(log)
    print(f"{len(log.splitlines())} lines -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
