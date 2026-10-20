"""Where the launcher keeps the player's things (design/M6-playable-build.md).

    Documents/SOTN Co-op/
        settings.json
        playthroughs/<id>/         A.mcd, B.mcd, session.coop, playthrough.json, savestates/
        reports/                   F9 bug reports (zips)
        debug-starts/              savestates made from the player's own disc, to start anywhere

COOP_DATA overrides the folder (tests, portable installs). Nothing here is ever deleted by the
launcher, except a playthrough's savestates when the player asks, and confirms (D69).
"""

import json
import os
from pathlib import Path


def data_dir():
    if os.environ.get("COOP_DATA"):
        d = Path(os.environ["COOP_DATA"])
    else:
        docs = Path.home() / "Documents"
        d = (docs if docs.exists() else Path.home()) / "SOTN Co-op"
    d.mkdir(parents=True, exist_ok=True)
    return d


def playthroughs_dir():
    d = data_dir() / "playthroughs"
    d.mkdir(exist_ok=True)
    return d


def reports_dir():
    d = data_dir() / "reports"
    d.mkdir(exist_ok=True)
    return d


def debug_starts_dir():
    d = data_dir() / "debug-starts"
    d.mkdir(exist_ok=True)
    return d


def folder_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except OSError:
                pass
    return total


def human(n):
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024


DEFAULTS = {"disc": None, "bios": None, "music": "auto", "aggro": 50, "pads": [None, None]}


def load_settings():
    p = data_dir() / "settings.json"
    s = dict(DEFAULTS)
    if p.exists():
        try:
            s.update(json.loads(p.read_text()))
        except ValueError:
            pass
    return s


def save_settings(s):
    p = data_dir() / "settings.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=1))
    tmp.replace(p)


def open_folder(path):
    """Shows the folder in the system's file manager."""
    import subprocess
    import sys
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
