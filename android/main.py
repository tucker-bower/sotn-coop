"""SOTN Co-op for Android (design/M9-android.md): python-for-android starts this.

The app's folder holds the same files as the PC installer's app/ folder (android/build.sh):
the launcher, the harness's game and session code, the link, the patcher, and the SwanStation
core for each CPU (bin/<abi>/). The player's data (discs, playthroughs, savestates) lives in the
app's own folder a PC can see over USB (Android/data/org.sotncoop.app/files).

Test mode (android/test_pair.py): a coop-ux.json in the app's private folder (where a test can put
files, with run-as) runs one launcher/uxdriver.py script instead of the launcher; paths in it are
relative to that folder, and the report lands in ux/<script>/ there.
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
# SDL sets the activity's orientation when it makes the window, over the manifest's: landscape.
os.environ["SDL_IOS_ORIENTATIONS"] = "LandscapeLeft LandscapeRight"

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


def no_system_fonts():
    """pygame looks for system fonts with fc-list, which Android doesn't let an app run: none, so
    SysFont uses pygame's own font."""
    import pygame.sysfont
    pygame.sysfont.is_init = True


def main():
    no_system_fonts()
    priv = Path(os.environ.get("ANDROID_PRIVATE", HERE.parent))
    test = priv / "coop-ux.json"
    if test.exists():
        cfg = json.loads(test.read_text())
        test.rename(priv / "coop-ux.json.used")
        here = lambda p: str(priv / p) if p and not os.path.isabs(p) else p  # noqa: E731
        env = {k: here(v) if k.endswith(("_CODE", "_FILE")) else v for k, v in cfg.get("env", {}).items()}
        if "COOP_DATA_FILE" in env:  # the launcher's data folder, for the test (settings in it)
            env["COOP_DATA"] = env.pop("COOP_DATA_FILE")
        os.environ.update(env)
        import uxdriver
        rep = uxdriver.run(cfg["script"], priv / "ux" / cfg["script"], here(cfg.get("disc")))
        print("COOP-UX-DONE", json.dumps({"passed": rep["passed"], "error": rep["error"]}), flush=True)
        return
    import app
    app.main()


main()
