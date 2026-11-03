"""What the app reads at run time is in both builds: the installer's (scripts/build_release.sh) and
the Android app's (android/build.sh). 0.13 to 0.16.0's APK left out maria-partner.bps, and every
game start on Android with Maria's disc chosen crashed. No games run.

    python launcher/test_ship_lists.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "launcher"))


def maria_files(script):
    """The files a build script copies from .env/out/maria."""
    m = re.search(r'/\.env/out/maria/\{([^}]*)\}', (ROOT / script).read_text())
    return set(m.group(1).split(",")) if m else set()


def main():
    read = set(re.findall(r'"(maria[\w-]*\.(?:bps|json))"', (ROOT / "launcher" / "characters.py").read_text()))
    failures = []
    for script in ("scripts/build_release.sh", "android/build.sh"):
        missing = read - maria_files(script)
        print(("ok   " if not missing else "FAIL ") + f"{script} ships Maria's {sorted(read)}" +
              (f": missing {sorted(missing)}" if missing else ""))
        if missing:
            failures.append(script)
    if len(read) < 5:
        print(f"FAIL found only {sorted(read)} in launcher/characters.py")
        failures.append("characters.py")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
