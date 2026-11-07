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


def patcher_files(script):
    """The patcher files a build script copies."""
    m = re.search(r'/patcher/\{([^}]*)\}\.py', (ROOT / script).read_text())
    shipped = {f"{n}.py" for n in m.group(1).split(",")} if m else set()
    return shipped | set(re.findall(r'/patcher/(\w+\.json)"', (ROOT / script).read_text()))


def patcher_needs():
    """The patcher modules the app imports (launcher/app.py's randomizer and patcher, and what
    they import from the patcher folder), plus the data files they read."""
    need, todo = set(), ["patcher.py", "randomizer.py"]
    while todo:
        f = todo.pop()
        if f in need:
            continue
        need.add(f)
        text = (ROOT / "patcher" / f).read_text()
        for mod in re.findall(r"^import (\w+)  # noqa: E402", text, re.M) + re.findall(r"^from (\w+) import", text, re.M):
            if (ROOT / "patcher" / f"{mod}.py").exists():
                todo.append(f"{mod}.py")
        need |= set(re.findall(r'"(\w+\.json)"', text)) - {"manifest.json"}
    return need


def main():
    read = set(re.findall(r'"(maria[\w-]*\.(?:bps|json))"', (ROOT / "launcher" / "characters.py").read_text()))
    failures = []
    for script in ("scripts/build_release.sh", "android/build.sh"):
        missing = patcher_needs() - patcher_files(script)
        print(("ok   " if not missing else "FAIL ") + f"{script} ships the patcher's {sorted(patcher_needs())}" +
              (f": missing {sorted(missing)}" if missing else ""))
        if missing:
            failures.append(script)
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
