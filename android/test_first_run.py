"""An APK's first start as a new player has it, on the headless x86_64 emulator: installed fresh
(no data, no disc), opened, and still running 30 s later with no Python error in its log and
something on the screen. 1.2.0 closed itself here on every Android device (#323).
scripts/release.py --android runs it before uploading an APK.

    python android/test_first_run.py [apk]    (default: the newest .env/android/*.apk)

Its log and a picture of the screen land in .env/out/android_first_run/. Nothing appears on the
desktop (the emulator has no window)."""

import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_pair import ADB, PKG, ROOT, adb, boot  # noqa: E402

OUT = ROOT / ".env" / "out" / "android_first_run"
SECONDS = 30
failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def colours(serial):
    """How many colours are on the screen (a raw screencap: a header, then RGBA rows)."""
    raw = subprocess.run([ADB, "-s", serial, "exec-out", "screencap"], capture_output=True, check=True).stdout
    w, h = struct.unpack("<II", raw[:8])
    pixels = raw[len(raw) - w * h * 4:]
    return len({pixels[i:i + 4] for i in range(0, len(pixels), 4 * 97)})


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    apk = Path(args[0]) if args else max((ROOT / ".env" / "android").glob("*.apk"), key=lambda p: p.stat().st_mtime)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{apk.name} on the emulator")
    started = "emulator-5554" not in subprocess.run([ADB, "devices"], capture_output=True, text=True).stdout
    serial = boot("coopA", 5554)
    try:
        adb(serial, "uninstall", PKG, check=False)
        # Right after the emulator boots, an uninstall can leave the app's external folder (its
        # launcher.log, settings) owned by the old install's user: the new one can't write there.
        external = f"/storage/emulated/0/Android/data/{PKG}"
        adb(serial, "shell", "rm", "-rf", external, check=False)
        if adb(serial, "shell", "ls", "-d", external, check=False).strip() == external:
            raise SystemExit(f"{external} is left from an earlier install: not a fresh start")
        adb(serial, "install", "-r", str(apk))
        adb(serial, "logcat", "-c")
        adb(serial, "shell", "monkey", "-p", PKG, "-c", "android.intent.category.LAUNCHER", "1")
        alive = True
        for _ in range(SECONDS // 2):
            time.sleep(2)
            if not adb(serial, "shell", "pidof", PKG, check=False).strip():
                alive = False
                break
        log = adb(serial, "logcat", "-d")
        (OUT / "logcat.txt").write_text(log)
        python = [line for line in log.splitlines() if " python  :" in line]
        errors = [line.split(" python  : ", 1)[1] for line in python if "Traceback" in line or "Error:" in line]
        check(alive, f"the app is still running {SECONDS} s after it opens")
        check(not errors, "no Python error in its log" + "".join(f"\n     {e}" for e in errors[-3:]))
        if alive:
            (OUT / "screen.png").write_bytes(subprocess.run([ADB, "-s", serial, "exec-out", "screencap", "-p"],
                                                            capture_output=True, check=True).stdout)
            n = colours(serial)
            check(n > 4, f"its first screen is drawn ({n} colours): {OUT / 'screen.png'}")
    finally:
        if started:
            adb(serial, "emu", "kill", check=False)
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
