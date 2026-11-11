"""Where the launcher keeps the player's things (design/M6-playable-build.md, launcher-overhaul.md).

Installed, everything is in the folder the player chose (D196):
    <their folder>/sotn-coop/app, python    the program (an update replaces them)
    <their folder>/sotn-coop/data/          everything below (an update or an uninstall leaves it)
A dev checkout uses Documents/SOTN Co-op/, and Android the app's own storage (COOP_DATA).

    data/
        settings.json
        castles/<name>/            A.mcd, B.mcd, castle.coop, castle.json, savestates/ (design/M11)
        playthroughs/              from before 0.10: kept, not listed
        reports/                   F9 bug reports (zips)
        debug-starts/              savestates made from the player's own disc, to start anywhere
        characters/maria.blob      Maria, made from the player's own Dracula X Chronicles disc (M8)
        art/                       the game's own art, music and sounds for the menus, from the player's disc

        discs/                     the player's PlayStation disc (a copy) and the co-op disc made from it
        game-discs/                their game discs: mods, and the images of the three used last
        art/                       the game's art, music and sounds for the menus, from their disc

COOP_DATA overrides the folder (tests, Android). Nothing here is ever deleted by the launcher,
except what the player asks for and confirms (D69). Settings keep a path inside the folder
relative to it, so the folder can be moved, to another drive or PC.
"""

import json
import os
from pathlib import Path


def install_root():
    """The folder the player installed to (it holds app/ and python/), or None in a dev checkout.
    COOP_INSTALL_ROOT stands in for it (tests)."""
    if os.environ.get("COOP_INSTALL_ROOT"):
        return Path(os.environ["COOP_INSTALL_ROOT"])
    root = Path(__file__).resolve().parent.parent.parent
    return root if (root / "python" / "pythonw.exe").exists() and (root / "app").is_dir() else None


def old_data_dir():
    """Where data lived before it moved into the install (D196): Documents/SOTN Co-op."""
    docs = Path.home() / "Documents"
    return (docs if docs.exists() else Path.home()) / "SOTN Co-op"


def data_dir():
    if os.environ.get("COOP_DATA"):
        d = Path(os.environ["COOP_DATA"])
    elif install_root() and not os.environ.get("COOP_DATA_OLD"):  # (COOP_DATA_OLD: the move from Documents failed)
        d = install_root() / "data"
    else:
        d = old_data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def castles_dir():
    d = data_dir() / "castles"
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


def characters_dir():
    d = data_dir() / "characters"
    d.mkdir(exist_ok=True)
    return d


def art_dir():
    """The game's own art and sounds for the menus, read from the player's disc (gameart.py)."""
    d = data_dir() / "art"
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


DEFAULTS = {"disc": None, "bios": None, "music": "auto", "pads": [None, None], "partner_hp": True}


HERE = "@data/"  # a stored path inside the data folder: relative to it, so the folder can move


def _stored(value, folder, out):
    """Settings as written: paths inside the data folder made relative (out=True), or back (False)."""
    if isinstance(value, dict):
        return {k: _stored(v, folder, out) for k, v in value.items()}
    if isinstance(value, list):
        return [_stored(v, folder, out) for v in value]
    if isinstance(value, str):
        if out:
            try:
                rel = Path(value).relative_to(folder)
                return HERE + rel.as_posix() if Path(value).is_absolute() else value
            except ValueError:
                return value
        if value.startswith(HERE):
            return str(folder / value[len(HERE):])
    return value


def load_settings():
    p = data_dir() / "settings.json"
    s = dict(DEFAULTS)
    if p.exists():
        try:
            s.update(_stored(json.loads(p.read_text()), data_dir(), False))
        except ValueError:
            pass
    return s


def save_settings(s):
    p = data_dir() / "settings.json"
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(_stored(s, data_dir(), True), indent=1))
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


def open_url(url):
    """Shows a web page in the system's browser."""
    import webbrowser
    try:
        if os.environ.get("COOP_OPEN_URL"):  # tests: written down, not opened
            with open(os.environ["COOP_OPEN_URL"], "a") as f:
                f.write(url + "\n")
            return
        from platform_android import ANDROID
        if ANDROID:  # (Python's webbrowser has no browser to call there)
            import platform_android
            platform_android.open_url(url)
            return
        webbrowser.open(url)
    except Exception:  # noqa: BLE001 - no browser: nothing to do
        pass
