"""One folder for everything (D196, design/launcher-overhaul.md criteria 23 and 24), with made-up
files in a temporary home: installed, the data folder is inside the install; paths in it are kept
relative, so the folder can move; a player's Documents folder moves in whole, or not at all
(a full disk, a copy that fails), and a disc is copied in with every file its .cue names.

    python launcher/test_one_folder.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent / "patcher")]

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for k in ("COOP_DATA", "COOP_DATA_OLD"):
            os.environ.pop(k, None)
        os.environ["HOME"] = os.environ["USERPROFILE"] = str(tmp / "home")
        (tmp / "home" / "Documents").mkdir(parents=True)
        install = tmp / "Games" / "sotn-coop"
        os.environ["COOP_INSTALL_ROOT"] = str(install)
        import discs
        import move
        import paths
        check(paths.data_dir() == install / "data", "installed: the data folder is inside the install")

        # Paths in the data folder are kept relative
        s = paths.load_settings()
        s.update(disc=str(install / "data" / "discs" / "sotn (Co-op).cue"), dxc_iso="/elsewhere/dxc.iso",
                 game_discs=[{"built": {"cue": str(install / "data" / "game-discs" / "a" / "x.cue")}}])
        paths.save_settings(s)
        raw = json.loads((install / "data" / "settings.json").read_text())
        check(raw["disc"] == "@data/discs/sotn (Co-op).cue" and raw["dxc_iso"] == "/elsewhere/dxc.iso"
              and raw["game_discs"][0]["built"]["cue"] == "@data/game-discs/a/x.cue",
              "a path inside the folder is stored relative to it, one outside as it is")
        moved_to = tmp / "D" / "sotn-coop"
        shutil.copytree(install, moved_to)
        os.environ["COOP_INSTALL_ROOT"] = str(moved_to)
        s = paths.load_settings()
        check(s["disc"] == str(moved_to / "data" / "discs" / "sotn (Co-op).cue") and s["dxc_iso"] == "/elsewhere/dxc.iso",
              "the whole folder moved to another drive: its paths follow it")
        os.environ["COOP_INSTALL_ROOT"] = str(install)

        # A disc is copied in, every file its .cue names
        src = tmp / "rips"
        src.mkdir()
        (src / "SOTN (Track 1).bin").write_bytes(b"1" * 5000)
        (src / "SOTN (Track 2).bin").write_bytes(b"2" * 300)
        (src / "SOTN.cue").write_text('FILE "SOTN (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\nFILE "SOTN (Track 2).bin" BINARY\n  TRACK 02 AUDIO\n')
        seen = []
        copy = discs.copy_in(src / "SOTN.cue", paths.data_dir() / "discs", lambda d, t: seen.append((d, t)))
        check(copy == install / "data" / "discs" / "SOTN.cue" and (copy.parent / "SOTN (Track 2).bin").stat().st_size == 300
              and seen[-1][0] == seen[-1][1] > 5300 and (src / "SOTN.cue").exists(),
              "a disc is copied in with its tracks, with progress, and the player's own stays")
        check(discs.copy_in(copy, paths.data_dir() / "discs") == copy, "one already there isn't copied again")

        # A player's Documents folder moves in
        shutil.rmtree(install / "data")
        old = paths.old_data_dir()
        (old / "castles" / "Tucker").mkdir(parents=True)
        (old / "castles" / "Tucker" / "castle.coop").write_bytes(b"save" * 100)
        (old / "launcher.log").write_text("the old log")
        (old / "settings.json").write_text(json.dumps({"disc": "/rips/SOTN (Co-op).cue", "art": str(old / "art" / "x.png")}))
        paths.data_dir()  # (this run's log folder: there before the move, as in the app)
        check(move.needed(), "Documents has a player's things, the install's folder hasn't: they move")

        real_usage = shutil.disk_usage
        shutil.disk_usage = lambda p: type("U", (), {"free": 10})()
        ok, said = move.move()
        shutil.disk_usage = real_usage
        check(not ok and os.environ.pop("COOP_DATA_OLD", None) and (old / "castles" / "Tucker" / "castle.coop").exists()
              and not (install / "data" / "settings.json").exists() and "space" in said,
              f"a disk too full: nothing moves, the old folder is used, and the player is told ({said[:60]}...)")

        real_copy, calls = shutil.copy2, []

        def failing(a, b, **kw):
            calls.append(a)
            if len(calls) == 2:
                raise OSError("the disk went away")
            return real_copy(a, b, **kw)
        shutil.copy2 = failing
        ok, said = move.move()
        shutil.copy2 = real_copy
        check(not ok and os.environ.pop("COOP_DATA_OLD", None) and not (install / "data.moving").exists()
              and not (install / "data" / "settings.json").exists() and (old / "settings.json").exists(),
              "a copy that fails half way: nothing half-moved is left, the old folder stays whole")

        ok, said = move.move()
        new = install / "data"
        st = json.loads((new / "settings.json").read_text())
        check(ok and (new / "castles" / "Tucker" / "castle.coop").read_bytes() == b"save" * 100,
              "then it moves: every castle and save")
        check(st["disc"] == "/rips/SOTN (Co-op).cue" and st["art"] == str(new / "art" / "x.png"),
              "paths into the old folder now point into the new one; others stay")
        left = sorted(p.name for p in old.rglob("*"))
        check(left == sorted(["launcher.log", move.NOTE]) and str(new) in (old / move.NOTE).read_text(),
              f"the old folder keeps a note saying where everything went (and its old log): {left}")
        check(not move.needed(), "and it moves once")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
