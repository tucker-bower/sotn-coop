"""Moves a player's things from Documents/SOTN Co-op into the install's data folder, once, on the
first launch after the update that put everything in one folder (D196, design/launcher-overhaul.md).

    needed() -> True if there's something to move
    move(progress) -> (moved?, what to tell the player)

Everything is copied, then checked file by file, and only then is the old copy removed, leaving a
note there saying where it went. If anything goes wrong first (a full disk, a file that can't be
read), what was copied is removed, the old folder stays in use for this run, and the player is told.
"""

import json
import os
import shutil
from pathlib import Path

import paths

NOTE = "Where did everything go.txt"
LOGS = {"launcher.log", "launcher-errors.log", "session.log"}  # this run's are open in the new folder: the old ones stay


def needed():
    root = paths.install_root()
    if not root or os.environ.get("COOP_DATA"):
        return False
    old, new = paths.old_data_dir(), root / "data"
    return (old / "settings.json").exists() and not (new / "settings.json").exists()


def _files(folder):
    return [p for p in Path(folder).rglob("*") if p.is_file() and p.name != NOTE and not (p.parent == Path(folder) and p.name in LOGS)]


def _merge(src, dst, last=None):
    """Moves src's files into dst, folder by folder; one dst has already is replaced. last (a
    name in src): moved after everything else, so it being there means the move finished."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.name == last:
            continue
        if item.is_dir():
            _merge(item, target)
        else:
            os.replace(item, target)
    if last and (src / last).exists():
        os.replace(src / last, dst / last)


def move(progress=None):
    old, new = paths.old_data_dir(), paths.install_root() / "data"
    if not (old / "settings.json").exists():  # moved already, or nothing there: nothing to do
        return True, ""
    files = _files(old)
    total = sum(f.stat().st_size for f in files)
    free = shutil.disk_usage(new.parent).free
    if free < total + (64 << 20):
        os.environ["COOP_DATA_OLD"] = "1"
        return False, (f"Your castles and saves are still in {old}: the SOTN Co-op folder's drive needs "
                       f"{(total - free) // (1 << 20) + 64} MB more to move them there. Free some space and start again.")
    staging = new.with_name("data.moving")
    shutil.rmtree(staging, ignore_errors=True)
    try:
        done = 0
        for f in files:
            target = staging / f.relative_to(old)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            done += f.stat().st_size
            if progress:
                progress(done, total)
        for f in files:  # checked before anything is removed
            if (staging / f.relative_to(old)).stat().st_size != f.stat().st_size:
                raise OSError(f"{f.name} didn't copy whole")
        # The settings' paths: those in the old folder are now in the new one
        p = staging / "settings.json"
        raw = json.loads(p.read_text())

        def moved(v):
            if isinstance(v, dict):
                return {k: moved(x) for k, x in v.items()}
            if isinstance(v, list):
                return [moved(x) for x in v]
            if isinstance(v, str):
                try:
                    return str(new / Path(v).relative_to(old))
                except ValueError:
                    return v
            return v
        raw = moved(raw)
        p.write_text(json.dumps(raw, indent=1))
        _merge(staging, new, last="settings.json")  # (the new folder exists already: this run's log is open in it)
        shutil.rmtree(staging, ignore_errors=True)
    except (OSError, ValueError) as e:
        shutil.rmtree(staging, ignore_errors=True)
        os.environ["COOP_DATA_OLD"] = "1"
        return False, f"Your castles and saves are still in {old}: they couldn't be moved ({e}). Everything works as before."
    for f in files:  # the copy is whole: the old one goes, and a note says where
        try:
            f.unlink()
        except OSError:
            pass
    for d in sorted((p for p in old.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass
    try:
        (old / NOTE).write_text(f"SOTN Co-op now keeps everything in one folder.\nYour castles, saves and settings are in:\n{new}\n")
    except OSError:
        pass
    return True, f"Your castles, saves and settings moved into the SOTN Co-op folder:\n{new}"
