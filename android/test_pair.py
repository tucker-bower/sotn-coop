"""M9 criterion 2 (design/M9-android.md): two Android devices play together. Two headless x86_64
emulators run the real app; each plays one launcher/uxdriver.py script (online_host,
online_join), from a fresh install: the disc picked and patched on the device, then Host / Join,
the lobby, and play with the partner connected.

    python android/test_pair.py [apk]       (default: the newest .env/android/*.apk)

The emulators can't reach each other directly (each is behind its own NAT on this PC), so the
joiner types the host's address as 10.0.2.2:PORT (this PC, from inside an emulator), which the
host's emulator forwards (adb emu redir): the ip:port way in, as across a router with a forwarded
port. Reports land in .env/out/android_pair/. Nothing appears on the desktop (no window)."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SDK = Path(os.environ.get("ANDROID_HOME", Path.home() / "android"))
ADB = str(SDK / "platform-tools" / "adb")
EMULATOR = str(SDK / "emulator" / "emulator")
PKG = "org.sotncoop.app"
EXT = f"/sdcard/Android/data/{PKG}/files"
PORT = 47000
DEVICES = {"A": ("coopA", 5554), "B": ("coopB", 5556)}
DISC = ROOT / "disks"
CUE = "Castlevania - Symphony of the Night (USA).cue"
BINS = ("Castlevania - Symphony of the Night (USA) (Track 1).bin",
        "Castlevania - Symphony of the Night (USA) (Track 2).bin")
OUT = ROOT / ".env" / "out" / "android_pair"


def adb(serial, *args, check=True, **kw):
    return subprocess.run([ADB, "-s", serial, *args], check=check, capture_output=True, text=True, **kw).stdout


def boot(avd, port):
    serial = f"emulator-{port}"
    if not os.access("/dev/kvm", os.R_OK | os.W_OK):  # WSL resets it; the kvm group needs a new login
        subprocess.run(["sudo", "-n", "chmod", "666", "/dev/kvm"], check=False)
    if serial not in subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout:
        subprocess.Popen([EMULATOR, "-avd", avd, "-no-window", "-no-audio", "-no-boot-anim", "-gpu",
                          "swiftshader_indirect", "-no-snapshot-save", "-port", str(port)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(200):
        if adb(serial, "shell", "getprop", "sys.boot_completed", check=False).strip() == "1":
            return serial
        time.sleep(3)
    raise RuntimeError(f"{avd} didn't boot")


def main():
    apk = Path(sys.argv[1]) if len(sys.argv) > 1 else max((ROOT / ".env" / "android").glob("*.apk"), key=os.path.getmtime)
    track = {b: next(DISC.glob("*Track 1).bin")) if "1" in b else next(DISC.glob("*Track 2).bin")) for b in BINS}
    serials = {k: boot(*v) for k, v in DEVICES.items()}
    print("booted", serials, flush=True)
    for who, serial in serials.items():
        adb(serial, "uninstall", PKG, check=False)
        adb(serial, "install", "-r", str(apk))
        adb(serial, "shell", "mkdir", "-p", f"{EXT}/discs")
        # The retail disc, as a player would have it (a .cue naming its two .bin files).
        local_cue = OUT / CUE
        OUT.mkdir(parents=True, exist_ok=True)
        local_cue.write_text("\n".join(
            [f'FILE "{BINS[0]}" BINARY', "  TRACK 01 MODE2/2352", "    INDEX 01 00:00:00",
             f'FILE "{BINS[1]}" BINARY', "  TRACK 02 AUDIO", "    INDEX 00 00:00:00", "    INDEX 01 00:02:00"]) + "\n")
        adb(serial, "push", str(local_cue), f"{EXT}/discs/{CUE}")
        for b in BINS:
            adb(serial, "push", str(track[b]), f"{EXT}/discs/{b}")
        print(who, "installed, disc pushed", flush=True)
    a, b = serials["A"], serials["B"]
    adb(a, "emu", "redir", "add", f"udp:{PORT}:{PORT}")
    code = OUT / "code.txt"
    code.write_text(f"10.0.2.2:{PORT}")
    adb(b, "push", str(code), f"{EXT}/code.txt")
    for who, script in (("A", "online_host"), ("B", "online_join")):
        cfg = {"script": script, "disc": f"{EXT}/discs/{CUE}",
               "env": {"COOP_UX_CODE": f"{EXT}/code{'' if who == 'B' else '-host'}.txt",
                       "COOP_PORT": str(PORT) if who == "A" else "0", "COOP_UX_NO_AUDIO": "1"}}
        f = OUT / f"coop-ux-{who}.json"
        f.write_text(json.dumps(cfg))
        adb(serials[who], "push", str(f), f"{EXT}/coop-ux.json")
        adb(serials[who], "logcat", "-c")
    for serial in (a, b):
        adb(serial, "shell", "am", "start", "-n", f"{PKG}/org.kivy.android.PythonActivity")
    results, t0 = {}, time.time()
    while len(results) < 2 and time.time() - t0 < 1800:
        for who, serial in serials.items():
            if who in results:
                continue
            log = adb(serial, "logcat", "-d", "-s", "python:I", check=False)
            for line in log.splitlines():
                if "COOP-UX-DONE" in line:
                    results[who] = json.loads(line.split("COOP-UX-DONE", 1)[1])
                elif "Python for android ended" in line and who not in results:
                    results[who] = {"passed": False, "error": "the app ended:\n" + "\n".join(log.splitlines()[-30:])}
        time.sleep(5)
    for who, serial in serials.items():
        script = "online_host" if who == "A" else "online_join"
        adb(serial, "pull", f"{EXT}/ux/{script}", str(OUT / who), check=False)
        (OUT / f"logcat-{who}.txt").write_text(adb(serial, "logcat", "-d", "-s", "python:*", check=False))
    print(json.dumps(results, indent=1))
    ok = len(results) == 2 and all(r.get("passed") for r in results.values())
    print("PASSED android_pair" if ok else "FAILED android_pair", f"({time.time() - t0:.0f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
