"""Castles (design/M11-castles.md): names, the joiner's copies, and the slot rules. No games run:
each "PC" is its own COOP_DATA folder.

    python launcher/test_castles.py
"""

import os
import struct
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from link.jointsave import SAVE_DATA_SIZE, JointSave, both_slots, read_session, save_fields, write_session  # noqa: E402

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


@contextmanager
def pc(folder):
    """Run as the PC whose Documents\\SOTN Co-op is `folder`."""
    old = os.environ.get("COOP_DATA")
    os.environ["COOP_DATA"] = str(folder)
    try:
        yield
    finally:
        if old is None:
            del os.environ["COOP_DATA"]
        else:
            os.environ["COOP_DATA"] = old


def blob(name="", stage=0x0C, level=1, exp=0, tag=0):
    """A SaveData with a typed name, a save room's stage, a level and XP (tag: tells them apart)."""
    b = bytearray(SAVE_DATA_SIZE)
    b[0x200:0x200 + len(name)] = name.encode()
    struct.pack_into("<h", b, 0x228, stage)
    struct.pack_into("<II", b, 0x238 + 0x284, level, exp)
    b[-1] = tag
    return bytes(b)


def main():
    from archive import Castle

    root = Path(tempfile.mkdtemp(prefix="coop-castles-"))
    a_pc, b_pc, c_pc = root / "A", root / "B", root / "C"
    created = time.mktime((2026, 10, 25, 21, 40, 0, 0, 0, -1))

    # Names (criterion 7)
    with pc(a_pc):
        x = Castle.new(created=created)
        check(x.name == "New castle_2026-10-25-21:40", f"a new castle is 'New castle_…' until its first save ({x.name})")
        x.saved([blob("Tucker", level=3), blob("Sam")])
        check(x.name == "Tucker_2026-10-25-21:40", f"its name is the typed name and the creation time ({x.name})")
        x.tidy()
        check(x.dir.name == "Tucker_2026-10-25-21-40" and x.dir.exists(),
              f"its folder is file-safe ({x.dir.name})")
        check(x.info["level"] == 3 and x.info["where"] == "Alchemy Laboratory", f"the list shows where and the level ({x.summary()})")
        named = Castle.new(created=created, name="Our run")
        named.saved([blob("Tucker")])
        check(named.name == "Our run_2026-10-25-21:40", f"a castle named when it's made keeps that name ({named.name})")
        named.tidy()
        later = Castle.new(created=created + 60)
        later.saved([blob("Ann")])
        x.saved([blob("Tucker")])
        check([c.info["id"] for c in Castle.all()][:2] == [x.info["id"], later.info["id"]], "the list is sorted by last played")

    # The joiner's copy (criteria 3 and 5): B joins A's castle
    meta = x.meta()
    with pc(b_pc):
        copy = Castle.receive(meta)
        check(copy.info["id"] == x.info["id"] and copy.info["received"], "B's copy has A's castle id")
        copy.saved([blob("Sam", tag=1), blob("Tucker", tag=2)], theirs=True)
        check(copy.name == x.name, f"and A's castle's name ({copy.name})")
        check(copy.summary().startswith("your partner's"), f"the list says whose it is ({copy.summary()})")
        again = Castle.receive(meta)
        check(again.dir == copy.dir, "B joins again: the same copy is brought up to date (it only ever received)")
        copy.played_here()  # B plays it solo
        third = Castle.receive(meta)
        check(third.dir != copy.dir and third.name == x.name + " (2)",
              f"after B played its copy, joining A again makes a new one ({third.name})")
        check(Castle(copy.dir).info["received"] is False, "and B's own one is left as it was")

    # Back on A: A's castle doesn't change by B's playing
    with pc(a_pc):
        check(Castle(x.dir).info["id"] == meta["id"] and Castle(x.dir).name == x.name, "A's castle is untouched")

    # Slot rules: slot 2 copies slot 1 when there's none; both load at the higher XP
    s1 = blob("Tucker", level=5, exp=900, tag=1)
    one = both_slots([s1])
    check(one[0] == s1 and one[1] == s1, "a castle with no slot 2: the partner gets a copy of slot 1")
    low = blob("Sam", level=2, exp=40, tag=2)
    two = both_slots([s1, low])
    check(save_fields(two[1])[3] == 900 and two[1][-1] == 2, "slot 2 behind on XP: it loads at slot 1's (its own gear)")

    # A save with no partner keeps the file's slot 2
    path = root / "solo.coop"
    write_session(path, [s1, low])

    class Alone:
        def save_seq(self):
            return self.seq

        def save_out(self):
            return blob("Tucker", level=6, exp=1200, tag=3)

        def partner_age(self):
            return 0xFFFF

        def save_block(self):
            return 0

        def self_presence(self):
            class P:
                flags = 0
            return P()

        def partner_presence(self):
            return self.self_presence()

    class NoHost:
        def take_control(self):
            return []

        def send_control(self, msg):
            raise AssertionError("solo: nothing is sent")

    m = Alone()
    m.seq = 0
    j = JointSave([m], path, host=NoHost())
    m.seq = 1
    j.tick()
    got = read_session(path)
    check(got[0][-1] == 3 and got[1] == low, "a solo save writes slot 1 and keeps slot 2")

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
