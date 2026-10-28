"""M9 criterion 2 (design/M9-android.md): two Android devices play together. Two headless x86_64
emulators run the real app; each plays one launcher/uxdriver.py script (online_host,
online_join), from a fresh install: the disc picked and patched on the device, then Host / Join,
the lobby, and play with the partner connected.

    python android/test_pair.py [apk]        (default: the newest .env/android/*.apk)
    python android/test_pair.py --pc [apk]   criterion 3: the PC launcher hosts, an emulator joins
    python android/test_pair.py --pc-join [apk]   criterion 3: an emulator hosts, the PC launcher joins
    python android/test_pair.py --room [apk]      as --pc-join, but the PC types the room code: they
                                                  meet on the real ntfy.sh (Tucker's Thor playtest)

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
PRIV = f"/data/data/{PKG}/files"  # the app's private folder: test files go there (run-as)
PORT = 47000
DEVICES = {"A": ("coopA", 5554), "B": ("coopB", 5556)}
DISC = ROOT / "disks"
CUE = "Castlevania - Symphony of the Night (USA).cue"
BINS = ("Castlevania - Symphony of the Night (USA) (Track 1).bin",
        "Castlevania - Symphony of the Night (USA) (Track 2).bin")
OUT = ROOT / ".env" / "out" / "android_pair"


def adb(serial, *args, check=True, **kw):
    return subprocess.run([ADB, "-s", serial, *args], check=check, capture_output=True, text=True, **kw).stdout


TMP = "/data/local/tmp/coop"
# The launcher's settings for the test (its data folder: the app's private one, so a test can
# reach it). The emulators draw in software (no GPU), so the games are scaled in one pass
# (COOP_ONE_PASS, display.py: a test switch, not a setting).
SETTINGS = {}


def as_app(serial, command, check=True):
    """A shell command run as the app (its own files: run-as, as the build is debuggable)."""
    return adb(serial, "shell", f"run-as {PKG} sh -c '{command}'", check=check)


def put(serial, local, remote):
    """A file into the app's folder, as the app's own."""
    name = Path(local).name
    adb(serial, "push", str(local), f"{TMP}/{name}")
    adb(serial, "shell", "chmod", "755", f"{TMP}/{name}")
    as_app(serial, f"cp {TMP}/{name} {remote}")


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


def install(serial, apk, track):
    """A fresh install with the retail disc in the app's private folder. Files adb writes into the
    app's shared folder belong to adb's user, which the app can't read: they go to /data/local/tmp,
    and the app itself (run-as: the build is debuggable) copies them in."""
    adb(serial, "uninstall", PKG, check=False)
    adb(serial, "install", "-r", str(apk))
    local_cue = OUT / CUE
    local_cue.write_text("\n".join(
        [f'FILE "{BINS[0]}" BINARY', "  TRACK 01 MODE2/2352", "    INDEX 01 00:00:00",
         f'FILE "{BINS[1]}" BINARY', "  TRACK 02 AUDIO", "    INDEX 00 00:00:00", "    INDEX 01 00:02:00"]) + "\n")
    adb(serial, "shell", "mkdir", "-p", TMP)
    adb(serial, "push", str(local_cue), f"{TMP}/{CUE}")
    for b in BINS:
        adb(serial, "push", str(track[b]), f"{TMP}/{b}")
    adb(serial, "shell", "chmod", "-R", "755", TMP)
    as_app(serial, f"mkdir -p {PRIV}/discs && cp {TMP}/*.cue {TMP}/*.bin {PRIV}/discs/")


def script_on(serial, who, script, port):
    """Sets the app up to play one uxdriver script at its next start (android/main.py)."""
    cfg = {"script": script, "disc": f"discs/{CUE}",  # relative to the app's folder (main.py)
           "env": {"COOP_UX_CODE": "code.txt" if script == "online_join" else "code-host.txt",
                   "COOP_PORT": str(port), "COOP_PROFILE": "1", "COOP_ONE_PASS": "1",  # with sound, as players
                   "COOP_DATA_FILE": "data"}}
    f = OUT / f"coop-ux-{who}.json"
    f.write_text(json.dumps(cfg))
    put(serial, f, f"{PRIV}/coop-ux.json")
    settings = OUT / "settings.json"
    settings.write_text(json.dumps(SETTINGS))
    as_app(serial, f"rm -rf {PRIV}/data && mkdir -p {PRIV}/data")
    put(serial, settings, f"{PRIV}/data/settings.json")
    adb(serial, "logcat", "-c")


def pc_launcher(script, out, port, code_file, **env):
    """The PC's own launcher (headless) playing one uxdriver script, from a fresh data folder."""
    import shutil
    shutil.rmtree(out.parent / "pc-data", ignore_errors=True)  # a fresh install, as the device's
    env = dict(os.environ, COOP_PORT=str(port), COOP_UX_CODE=str(code_file), SDL_VIDEODRIVER="dummy",
               SDL_AUDIODRIVER="dummy", COOP_UX_NO_AUDIO="1", COOP_DATA=str(out.parent / "pc-data"), **env)
    pc_python = Path(os.environ.get("COOP_PYTHON", ROOT.parent / "sotn-decomp-coop" / ".venv" / "bin" / "python"))
    return subprocess.Popen([str(pc_python), str(ROOT / "launcher" / "uxdriver.py"), script, "--out", str(out)],
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # --pc: the PC hosts, emulator B joins; --pc-join: emulator A hosts, the PC joins (criterion 3)
    mode = ("pc" if "--pc" in sys.argv else "pc_join" if "--pc-join" in sys.argv
            else "room" if "--room" in sys.argv else "pair")
    name = {"pair": "android_pair", "pc": "android_pc", "pc_join": "android_pc_join", "room": "android_room"}[mode]
    apk = Path(args[0]) if args else max((ROOT / ".env" / "android").glob("*.apk"), key=os.path.getmtime)
    track = {b: DISC / b for b in BINS}  # the retail files (disks/ also holds a patched copy)
    global OUT, PORT
    OUT = OUT.with_name(name)
    PORT += {"pair": 0, "pc": 1, "pc_join": 2, "room": 3}[mode]  # a redirect (adb emu redir) may hold another's port
    OUT.mkdir(parents=True, exist_ok=True)
    devices = {"pair": "AB", "pc": "B", "pc_join": "A", "room": "A"}[mode]
    serials = {k: boot(*v) for k, v in DEVICES.items() if k in devices}
    print("booted", serials, flush=True)
    for who, serial in serials.items():
        install(serial, apk, track)
        print(who, "installed, disc pushed", flush=True)
    if "B" in serials:  # emulator B joins this PC's port, as 10.0.2.2 (this PC, from inside an emulator)
        code = OUT / "code.txt"
        code.write_text(f"10.0.2.2:{PORT}")
        put(serials["B"], code, f"{PRIV}/code.txt")
        script_on(serials["B"], "B", "online_join", 0)
    if "A" in serials:  # emulator A hosts; this PC's PORT is redirected to it
        adb(serials["A"], "emu", "redir", "add", f"udp:{PORT}:{PORT}")
        script_on(serials["A"], "A", "online_host", PORT)
    pc_proc = pc_who = None
    if mode == "pc":
        pc_who, pc_proc = "A", pc_launcher("online_host", OUT / "A", PORT, OUT / "code-host.txt")
    for serial in serials.values():
        adb(serial, "shell", "am", "start", "-n", f"{PKG}/org.kivy.android.PythonActivity")
    if mode in ("pc_join", "room"):  # once the device hosts (its room code written), the PC joins:
        # at the redirect, or by the room code (through ntfy.sh, as players do)
        for _ in range(360):
            room = as_app(serials["A"], f"cat {PRIV}/code-host.txt", check=False).strip()
            if room:
                break
            time.sleep(1)
        code = OUT / "code.txt"
        code.write_text(room if mode == "room" else f"127.0.0.1:{PORT}")
        pc_who, pc_proc = "B", pc_launcher("online_join", OUT / "B", 0, code)
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
        if pc_proc and pc_who not in results and pc_proc.poll() is not None:
            out = pc_proc.stdout.read()
            (OUT / "pc.txt").write_text(out)
            results[pc_who] = {"passed": pc_proc.returncode == 0, "error": None if pc_proc.returncode == 0 else out[-1500:]}
        time.sleep(5)
    for who, serial in serials.items():
        script = "online_host" if who == "A" else "online_join"
        (OUT / who).mkdir(parents=True, exist_ok=True)
        tar = subprocess.run([ADB, "-s", serial, "exec-out", f"run-as {PKG} tar c -C {PRIV}/ux {script}"],
                             capture_output=True).stdout
        subprocess.run(["tar", "x", "-C", str(OUT / who)], input=tar, check=False)
        (OUT / f"logcat-{who}.txt").write_text(adb(serial, "logcat", "-d", "-s", "python:*", check=False))
    print(json.dumps(results, indent=1)[:3000])
    ok = len(results) == 2 and all(r.get("passed") for r in results.values())
    print(f"PASSED {name}" if ok else f"FAILED {name}", f"({time.time() - t0:.0f} s)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
