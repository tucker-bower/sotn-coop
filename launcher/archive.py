"""Castles and their savestates (D69, design/M11-castles.md).

A castle is a playthrough anyone can continue: solo, on the couch, or hosted online with any
partner. It's a folder: the memory cards, the joint save (castle.coop: slot 1 is always the
player on this machine, slot 2 whoever plays with them), castle.json, and the savestates the
launcher made along the way. The joiner of an online session keeps a copy of the host's castle
(receive()): the same id and name, with its own state in slot 1. Savestates are made only at moments worth going back to (the first time
either player reaches a stage, a boss fight starting, quitting), never on a timer; a joint save
is its own restore point already. B's state is stored compressed against A's (the two games
are mostly alike): about 2 MB a moment, some 200 MB for a whole playthrough.
Each is compressed and gets a name of its own: the launcher never overwrites or deletes one.
The player can delete a playthrough's savestates from the Savestates screen (it asks first).
"""

import json
import os
import re
import time
import uuid
import zlib
from pathlib import Path

from link.jointsave import read_session, save_fields, write_session
from paths import castles_dir, folder_size

try:  # Python 3.14: zstd is in the standard library; it's smaller and faster than zlib
    from compression import zstd
except ImportError:
    zstd = None

STAGE_NAMES = {
    0x00: "Marble Gallery", 0x01: "Outer Wall", 0x02: "Long Library", 0x03: "Catacombs",
    0x04: "Olrox's Quarters", 0x05: "Abandoned Mine", 0x06: "Royal Chapel", 0x07: "Castle Entrance",
    0x08: "Center Cube", 0x09: "Underground Caverns", 0x0A: "Colosseum", 0x0B: "Castle Keep",
    0x0C: "Alchemy Laboratory", 0x0D: "Clock Tower", 0x41: "Castle Entrance", 0x1F: "Prologue",
    0x12: "Nightmare", 0x18: "Castle Keep", 0x1B: "Underground Caverns",  # the boss stages (BO6: Richter, BO3: Scylla)
}


def compress(data, like=None):
    """like: another state to compress against (B against A: the pair is self-contained)."""
    if zstd and like is not None:
        return b"ZPRE" + zstd.compress(data, 9, zstd_dict=zstd.ZstdDict(like, is_raw=True).as_prefix)
    if zstd:
        return b"ZSTD" + zstd.compress(data, 9)
    return b"ZLIB" + zlib.compress(data, 6)


def decompress(blob, like=None):
    kind, body = blob[:4], blob[4:]
    if kind == b"ZPRE":
        return zstd.decompress(body, zstd_dict=zstd.ZstdDict(like, is_raw=True).as_prefix)
    if kind == b"ZSTD":
        return zstd.decompress(body)
    if kind == b"ZLIB":
        return zlib.decompress(body)
    return blob  # an uncompressed state


def load_pair(a_file, b_file=None):
    """(A state, B state) from a savestate pair's files (or (A state, None) for a single-game online state)."""
    a = decompress(Path(a_file).read_bytes())
    if b_file is None or not Path(b_file).exists():
        return a, None
    return a, decompress(Path(b_file).read_bytes(), like=a)


def stage_name(stage):
    inverted = " (inverted)" if stage & 0x20 and stage < 0x40 else ""
    return STAGE_NAMES.get(stage & ~0x20 if inverted else stage, f"stage {stage:#04x}") + inverted


TESTS = "Test castles"  # their folder, in castles/ (Castle.all leaves it out: it has no castle.json)


def safe(text):
    """A folder name Windows and Android accept."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", text).strip(" .") or "castle"


class Castle:
    """info (castle.json): id, created, name (typed at SOTN's name entry; None until the first
    save), played, saves, stages, received (a copy from a host, not played here since)."""

    def __init__(self, folder):
        self.dir = Path(folder)
        self.states = self.dir / "savestates"
        self.states.mkdir(parents=True, exist_ok=True)
        self.info_path = self.dir / "castle.json"
        self.info = json.loads(self.info_path.read_text()) if self.info_path.exists() else {}

    @classmethod
    def new(cls, cid=None, created=None, name=None, received=False):
        created = created or time.time()
        stamp = time.strftime("%Y-%m-%d-%H-%M", time.localtime(created))
        folder = castles_dir() / safe(f"{name or 'New castle'}_{stamp}")
        k = 2
        while folder.exists():  # never reuse a folder
            folder = castles_dir() / safe(f"{name or 'New castle'}_{stamp} ({k})")
            k += 1
        c = cls(folder)
        c.info = {"id": cid or uuid.uuid4().hex[:16], "created": created, "name": name, "saves": 0,
                  "stages": [], "received": received}
        c.save_info()
        return c

    @classmethod
    def all(cls):
        out = [cls(d) for d in castles_dir().iterdir() if d.is_dir() and (d / "castle.json").exists()]
        return sorted(out, key=lambda c: c.info.get("played", c.info.get("created", 0)), reverse=True)

    @classmethod
    def tests(cls):
        """The test castles (Tucker, 2026-10-28): one outside each boss and before each story scene,
        in story order. They're templates: playing one plays a fresh copy (fresh_copy)."""
        d = castles_dir() / TESTS
        out = [cls(x) for x in d.iterdir() if (x / "castle.json").exists()] if d.exists() else []
        return sorted(out, key=lambda c: c.info.get("order", 0))

    @classmethod
    def make_test(cls, name, save, start, order, about):
        """A test castle from a debug start's joint save (debugstarts.py): `start` (stage, room,
        x, y) is where its players arrive, once their save has loaded, until its first save (the
        save alone would put them in the room's middle)."""
        folder = castles_dir() / TESTS / safe(name.replace(":", " -"))
        c = cls(folder)
        name_in_save, stage, level, _ = save_fields(save)
        c.info = {"id": uuid.uuid4().hex[:16], "created": time.time(), "name": name, "saves": 0, "stages": [],
                  "received": False, "test": True, "order": order, "about": about, "start": list(start),
                  "where": stage_name(stage), "level": level}
        write_session(c.joint_save, [save])
        c.save_info()
        return c

    def fresh_copy(self):
        """A test castle to play: a new castle with its save and start (the test one stays as made)."""
        c = Castle.new(name=self.info["name"])
        write_session(c.joint_save, read_session(self.joint_save))
        for k in ("start", "where", "level", "about"):
            c.info[k] = self.info.get(k)
        c.save_info()
        return c

    @classmethod
    def receive(cls, meta):
        """The joiner's copy of the host's castle (meta: its id, name, created). The copy that
        only ever received is brought up to date; one this player has played since (solo, or
        hosting it) is never touched: a new copy then, "… (2)" (design/M11: nothing a player
        played is overwritten)."""
        same = [c for c in cls.all() if c.info.get("id") == meta["id"]]
        for c in same:
            if c.info.get("received"):
                if meta.get("name") and not c.info.get("name"):
                    c.info["name"] = meta["name"]
                return c
        c = cls.new(meta["id"], meta.get("created"), meta.get("name"), received=True)
        c.info["joined"] = True  # for the list: it began as the partner's castle
        c.save_info()
        if same:
            c.info["copy"] = len(same) + 1
            c.save_info()
        return c

    def meta(self):
        """What a host tells its partner about this castle (in its HELO)."""
        return {"id": self.info["id"], "name": self.info.get("name"), "created": self.info["created"]}

    def played_here(self):
        """This player is playing it as their own (solo, couch, hosting): copies from a host go
        to another entry from now on."""
        self.info["received"] = False
        self.save_info()

    def saved(self, blobs, theirs=False):
        """A joint save was written (link/jointsave.py on_write). theirs: the castle is the
        partner's (this is the joiner's copy): its name comes from the host's save, slot 2."""
        name, stage, level, _ = save_fields(blobs[1] if theirs and len(blobs) > 1 else blobs[0])
        if name and not self.info.get("name"):
            self.info["name"] = name
        self.info.pop("start", None)  # a test castle: from its first save on, it goes on from there
        self.info["saves"] = self.info.get("saves", 0) + 1
        self.info["where"], self.info["level"] = stage_name(stage), level
        self.save_info()

    def save_info(self):
        self.info["played"] = time.time()
        tmp = self.info_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.info, indent=1))
        tmp.replace(self.info_path)

    def tidy(self):
        """After a session: the folder takes the castle's name once it has one (Windows can't
        rename a folder while the game has files in it open)."""
        want = castles_dir() / safe(self.name.replace(":", "-"))
        if want != self.dir and not want.exists() and self.info.get("name"):
            try:
                self.dir.rename(want)
                self.__init__(want)
            except OSError:
                pass

    @property
    def name(self):
        """Tucker_2026-10-25-21:40 (the creation time: a castle never renames itself)."""
        stamp = time.strftime("%Y-%m-%d-%H:%M", time.localtime(self.info.get("created", 0)))
        copy = f" ({self.info['copy']})" if self.info.get("copy") else ""
        return f"{self.info.get('name') or 'New castle'}_{stamp}{copy}"

    def summary(self):
        """For the castle list: whose (a copy of a partner's), where, level, last played."""
        bits = ["your partner's" if self.info.get("joined") or self.info.get("received") else None, self.info.get("where"), f"Lv {self.info['level']}" if self.info.get("level") else None,
                "played " + time.strftime("%b %d, %H:%M", time.localtime(self.info.get("played", 0)))]
        return "  ·  ".join(b for b in bits if b)

    def card(self, who):
        return self.dir / f"{who}.mcd"

    @property
    def joint_save(self):
        return self.dir / "castle.coop"

    def savestate(self, event, games, where=""):
        """Both games' states (or one game's state online), now. Returns the files written."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        label = "".join(c if c.isalnum() or c in " -" else "_" for c in f"{event} {where}".strip())
        base = f"{stamp} {label}"
        k = 2
        while (self.states / f"{base} A.state.zst").exists():
            base = f"{stamp} {label} ({k})"
            k += 1
        states = [g.save_state() for g in games]
        a = states[0]
        pairs = [("A", compress(a))]
        if len(states) > 1:
            pairs.append(("B", compress(states[1], like=a)))
        written = []
        for who, blob in pairs:
            path = self.states / f"{base} {who}.state.zst"
            with open(path, "xb") as f:  # "x": fails rather than overwrite
                f.write(blob)
            written.append(path)
        if os.environ.get("COOP_BIOS"):  # which BIOS made it: a state loads only on its own BIOS
            (self.states / f"{base}.bios").write_text(os.environ["COOP_BIOS"])
        return written

    @staticmethod
    def state_bios(a_file, bundled_dir, default):
        """The BIOS a savestate pair was made with (its .bios note), found again if the install
        moved (a bundled BIOS by name). States from before 0.12 have no note: `default`."""
        note = Path(str(a_file)[:-len(" A.state.zst")] + ".bios")
        if not note.exists():
            return Path(default)
        made = Path(note.read_text().strip())
        if made.exists():
            return made
        return bundled_dir / made.name if (bundled_dir / made.name).exists() else Path(default)

    def savestate_pairs(self):
        """[(label, A file, B file or None)], newest first."""
        files = sorted(self.states.glob("* A.state.zst"), reverse=True)
        out = []
        for a in files:
            b = a.with_name(a.name[:-len(" A.state.zst")] + " B.state.zst")
            out.append((a.name[:-len(" A.state.zst")], a, b if b.exists() else None))
        return out

    def savestates_size(self):
        return folder_size(self.states)

    def delete_savestates(self):
        """Only when the player asks (and has confirmed): this playthrough's savestates."""
        for f in self.states.glob("*.state.zst"):
            f.unlink()


def total_savestates_size():
    return sum(p.savestates_size() for p in Castle.all())


class Moments:
    """Watches both games for moments worth a savestate (checked a few times a second)."""

    def __init__(self, playthrough):  # a Castle
        self.p = playthrough
        self.seen = set(playthrough.info.get("stages", []))
        self.boss = False

    def check(self, presences):
        """[(event, where)] for this check."""
        from link.mailbox import BOSS, IN_PLAY
        out = []
        for pres in presences:
            if pres.flags & IN_PLAY and pres.stage not in self.seen and pres.stage != 0x1F:
                self.seen.add(pres.stage)
                self.p.info["stages"] = sorted(self.seen)
                out.append(("New area", stage_name(pres.stage)))
        boss = any(p.flags & BOSS for p in presences)
        if boss and not self.boss:
            stage = next(p.stage for p in presences if p.flags & BOSS)
            out.append(("Boss fight", stage_name(stage)))
        self.boss = boss
        return out
