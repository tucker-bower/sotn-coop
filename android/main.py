"""SOTN Co-op for Android (design/M9-android.md): python-for-android starts this.

The app's folder holds the same files as the PC installer's app/ folder (android/build.sh):
the launcher, the harness's game and session code, the link, the patcher, and the SwanStation
core for each CPU (bin/<abi>/). The player's data (discs, playthroughs, savestates) lives in the
app's own folder a PC can see over USB (Android/data/org.sotncoop.app/files).

Test mode (android/test_pair.py): a coop-ux.json there runs one launcher/uxdriver.py script
instead of the launcher, and its report lands in ux/<script>/ next to it.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / d) for d in ("launcher", "harness", "patcher")] + [str(HERE)]

import platform_android  # noqa: E402

EXT = platform_android.external_dir()
os.environ.setdefault("COOP_DATA", str(EXT))
os.environ["TMPDIR"] = str(platform_android.cache_dir())  # tempfile's default, /tmp, isn't there
os.environ.setdefault("COOP_BIOS", str(HERE / "bios" / "openbios.bin"))

# This device's core: the env manifest the harness reads (coop_env) names it.
ABI = platform_android.abi()
(HERE / "env.toml").write_text(f"""# Written by android/main.py at start: this device's CPU is {ABI}.
[paths]
repo = "."
disks = ".env/out/disc"
env = ".env"
[tools]
swanstation_core = "bin/{ABI}/swanstation_libretro_android.so"
bios_dir = "bios"
savestates = ".env/savestates"
out = ".env/out"
""")


def main():
    test = EXT / "coop-ux.json"
    if test.exists():
        cfg = json.loads(test.read_text())
        test.rename(EXT / "coop-ux.json.used")
        os.environ.update(cfg.get("env", {}))
        import uxdriver
        rep = uxdriver.run(cfg["script"], EXT / "ux" / cfg["script"], cfg.get("disc"))
        print("COOP-UX-DONE", json.dumps({"passed": rep["passed"], "error": rep["error"]}), flush=True)
        return
    import app
    app.main()


main()
