"""A full disk (#277): nothing the launcher writes is left half-written, a save that can't be
written keeps the last one, and nothing crashes. Made-up files in a temporary folder, and a disk
that's full from a chosen moment on (writes fail with ENOSPC, as Windows reports them).

    python launcher/test_disk_full.py
"""

import builtins
import errno
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


class FullDisk:
    """While on: a file opened for writing takes `room` more bytes, then fails as a full disk does."""

    def __init__(self, room=0):
        self.room, self.real = room, builtins.open

    def __enter__(self):
        disk = self

        class Writer:
            def __init__(self, f):
                self.f = f

            def write(self, data):
                n = len(data)
                if n > disk.room:
                    self.f.write(bytes(data[:disk.room]) if isinstance(data, (bytes, bytearray, memoryview)) else data[:disk.room])
                    disk.room = 0
                    raise OSError(errno.ENOSPC, "No space left on device")
                disk.room -= n
                return self.f.write(data)

            def __getattr__(self, name):
                return getattr(self.f, name)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.f.close()

        def fake_open(file, mode="r", *args, **kwargs):
            f = disk.real(file, mode, *args, **kwargs)
            return Writer(f) if any(c in mode for c in "wxa") else f

        builtins.open = fake_open
        self.io_open, Path.write_bytes = Path.write_bytes, lambda p, data: fake_open(p, "wb").write(data) and None
        return self

    def __exit__(self, *exc):
        builtins.open = self.real
        Path.write_bytes = self.io_open


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        os.environ["COOP_DATA"] = str(tmp / "data")
        os.environ.pop("COOP_INSTALL_ROOT", None)
        import discs
        import paths
        from link.jointsave import read_session, write_session
        from link.mailbox import SAVE_DATA_SIZE

        # --- a disc copy that runs out of space leaves no .part behind (it held every free byte)
        src = tmp / "outside" / "game.bin"
        src.parent.mkdir()
        src.write_bytes(os.urandom(3 << 20))
        inside = tmp / "data" / "discs"
        with FullDisk(room=1 << 20):
            try:
                discs.copy_in(src, inside)
                check(False, "a disc copy on a full disk fails")
            except OSError as e:
                check(e.errno == errno.ENOSPC, "a disc copy on a full disk fails")
        check(not list(inside.glob("*.part")) and not (inside / "game.bin").exists(),
              "...and leaves nothing behind: no .part holding the space")
        (inside / "game.bin.part").write_bytes(b"x" * 100)
        (inside / "sotn (Co-op) track1.tmp").write_bytes(b"x" * 100)
        check(sorted(f.name for f in discs.leftovers(inside)) == ["game.bin.part", "sotn (Co-op) track1.tmp"],
              "an older version's stopped copy is found, to be removed at startup")

        # --- the copy-in at startup: leftovers removed, and no copy without room for it
        import app
        logs = []

        class Fake:
            settings = {"disc_source": str(src)}
            ui_wait = None

        real = (paths.install_root, shutil.disk_usage)
        app.paths.install_root = lambda: tmp
        app.shutil.disk_usage = lambda p: type("U", (), {"free": 5 << 20})()
        app.log.warning = lambda *a: logs.append(a[0] % a[1:])
        try:
            app.Launcher.copy_disc_in(Fake())
        finally:
            app.paths.install_root, app.shutil.disk_usage = real
        check(not discs.leftovers(inside), "at startup, the leftovers are removed")
        check(any("needed" in m for m in logs) and Fake.settings == {"disc_source": str(src)},
              "with too little room, the disc isn't copied: it stays where it is")

        # --- the joint save: whole or not at all
        save = tmp / "castle" / "castle.coop"
        blob = (bytes(range(256)) * (SAVE_DATA_SIZE // 256 + 1))[:SAVE_DATA_SIZE]
        write_session(save, [blob])
        before = save.read_bytes()
        with FullDisk(room=100):
            try:
                write_session(save, [bytes(SAVE_DATA_SIZE)])
            except OSError:
                pass
        check(save.read_bytes() == before and read_session(save) == [blob], "a joint save on a full disk keeps the last save")
        check(not list(save.parent.glob("*.tmp")), "...and leaves no temporary file")

        from link.jointsave import JointSave
        j = JointSave([], save)
        with FullDisk(room=0):
            j._write([bytes(SAVE_DATA_SIZE), None])
        check(isinstance(j.error, OSError) and j.saves == 0, "JointSave says the save wasn't written, and doesn't crash")

        # --- memory cards and other files written whole
        card = tmp / "castle" / "A.mcd"
        card.write_bytes(b"MC" + bytes(131070))
        with FullDisk(room=1000):
            try:
                paths.write_atomic(card, b"MC" + b"\x01" * 131070)
            except OSError:
                pass
        check(card.read_bytes() == b"MC" + bytes(131070), "a memory card on a full disk keeps the last card")

        # --- a castle: its savestate leaves no half moment, and its info survives
        from archive import Castle
        c = Castle.new(name="Test")
        info = json.loads(c.info_path.read_text())

        class Game:
            def save_state(self):
                return os.urandom(1 << 20)

        with FullDisk(room=1000):
            try:
                c.savestate("New area", [Game()])
                check(False, "a savestate on a full disk fails")
            except OSError:
                check(True, "a savestate on a full disk fails")
            c.info["where"] = "Somewhere else"
            c.save_info()  # never raises
        check(not list(c.states.glob("*")), "...and leaves no half-written moment")
        check(json.loads(c.info_path.read_text())["name"] == info["name"], "the castle's info file stays whole")

        # --- the menu music cache
        import gamesound
        wav = tmp / "sound" / "music.wav"
        wav.parent.mkdir()
        with FullDisk(room=1000):
            try:
                gamesound.write_wav(wav, 22050, 2, gamesound.array("h", [0] * 100000))
            except OSError:
                pass
        check(not wav.exists() and not list(wav.parent.glob("*")), "music that can't be written leaves no broken .wav")

    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
