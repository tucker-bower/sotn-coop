"""D112 / design/M12-v1-release.md criterion 5: a debug-signed install's folder survives the switch
to the release key (android/device.py switch-key), on a headless x86_64 emulator.

    python android/test_key_switch.py <debug-signed apk> <release-signed apk>

The old app makes its folder (its first start), a castle goes in it, then switch_key backs it up,
uninstalls, installs the release-signed app and has it copy the folder back. Pass: every file is
back with the same contents, owned by the new app, and the app is signed with the release key."""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "harness")]
import device  # noqa: E402
import test_pair  # noqa: E402

SERIAL = "emulator-5554"
EXT = device.EXT
CASTLE = {"castles/Test_2026-10-27-20-00/castle.json": '{"name": "Test"}\n',
          "castles/Test_2026-10-27-20-00/A.mcd.txt": "slot A\n", "settings.json": '{"layout": "side"}\n'}


def adb(*args, check=False, capture_output=False, **kw):
    return subprocess.run([test_pair.ADB, "-s", SERIAL, *args], check=check, text=True,
                          capture_output=capture_output, **kw)


def sh(cmd):
    return adb("shell", cmd, capture_output=True).stdout


def main(old_apk, new_apk):
    test_pair.boot("coopA", 5554)
    adb("uninstall", device.PKG, capture_output=True)
    adb("install", str(old_apk), check=True, capture_output=True)
    adb("shell", "monkey", "-p", device.PKG, "-c", "android.intent.category.LAUNCHER", "1", capture_output=True)
    for _ in range(60):   # the old app's first start makes its folder
        if "launcher.log" in sh(f"ls {EXT}"):
            break
        time.sleep(1)
    adb("shell", "am", "force-stop", device.PKG, check=True)
    with tempfile.TemporaryDirectory() as tmp:   # the castle (the old app's files, as a player's would be)
        for rel, text in CASTLE.items():
            (Path(tmp) / Path(rel).name).write_text(text)
            sh(f"mkdir -p {EXT}/{Path(rel).parent}")
            adb("push", str(Path(tmp) / Path(rel).name), f"{EXT}/{rel}", check=True, capture_output=True)
    before = sorted(sh(f"cd {EXT} && find . -type f").split())
    uid_old = sh(f"stat -c %U {EXT}").strip()

    backup = HERE.parent / ".env" / "android" / time.strftime("backup-test-%Y%m%d-%H%M%S")
    device.switch_key(adb, Path(new_apk), backup, local=str)

    after = sorted(sh(f"cd {EXT} && find . -type f").split())
    uid_new = sh(f"stat -c %U {EXT}").strip()
    owners = set(sh(f"cd {EXT} && find . -type f -exec stat -c %U {{}} +").split())
    cert = subprocess.run([str(sorted((test_pair.SDK / "build-tools").glob("*/apksigner"))[-1]), "verify",
                           "--print-certs", str(new_apk)], capture_output=True, text=True).stdout
    from coop_env import ENV
    checks = {
        "every file back": set(before) <= set(after),
        "same contents": all(sh(f"cat {EXT}/{rel}") == text for rel, text in CASTLE.items()),
        "owned by the new app": owners == {uid_new},
        "release key": ENV["android"]["cert_sha256"] in cert,
    }
    for name, ok in checks.items():
        print(("PASS " if ok else "FAIL ") + name)
    print(f"files before {len(before)}, after {len(after)}; owner {uid_old} -> {uid_new}; backup {backup}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
