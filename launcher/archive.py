"""Playthroughs and their savestates (D69).

A playthrough is a folder: both memory cards, the joint save, and the savestates the launcher
made along the way. Savestates are made only at moments worth going back to (the first time
either player reaches a stage, a boss fight starting, quitting), never on a timer; a joint save
is its own restore point already. B's state is stored compressed against A's (the two games
are mostly alike): about 2 MB a moment, some 200 MB for a whole playthrough.
Each is compressed and gets a name of its own: the launcher never overwrites or deletes one.
The player can delete a playthrough's savestates from the Savestates screen (it asks first).
"""

import json
import time
import zlib
from pathlib import Path

from paths import folder_size, playthroughs_dir

try:  # Python 3.14: zstd is in the standard library; it's smaller and faster than zlib
    from compression import zstd
except ImportError:
    zstd = None

STAGE_NAMES = {
    0x00: "Marble Gallery", 0x01: "Outer Wall", 0x02: "Long Library", 0x03: "Catacombs",
    0x04: "Olrox's Quarters", 0x05: "Abandoned Mine", 0x06: "Royal Chapel", 0x07: "Castle Entrance",
    0x08: "Center Cube", 0x09: "Underground Caverns", 0x0A: "Colosseum", 0x0B: "Castle Keep",
    0x0C: "Alchemy Laboratory", 0x0D: "Clock Tower", 0x41: "Castle Entrance", 0x1F: "Prologue",
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


class Playthrough:
    def __init__(self, folder):
        self.dir = Path(folder)
        self.states = self.dir / "savestates"
        self.states.mkdir(parents=True, exist_ok=True)
        self.info_path = self.dir / "playthrough.json"
        self.info = json.loads(self.info_path.read_text()) if self.info_path.exists() else {}

    @classmethod
    def new(cls, name=None):
        stamp = time.strftime("%Y-%m-%d %H.%M")
        folder = playthroughs_dir() / stamp
        k = 2
        while folder.exists():  # never reuse a folder
            folder = playthroughs_dir() / f"{stamp} ({k})"
            k += 1
        p = cls(folder)
        p.info = {"name": name or f"Playthrough of {stamp}", "created": time.time(), "stages": []}
        p.save_info()
        return p

    @classmethod
    def all(cls):
        out = [cls(d) for d in playthroughs_dir().iterdir() if d.is_dir()]
        return sorted(out, key=lambda p: p.info.get("played", p.info.get("created", 0)), reverse=True)

    def save_info(self):
        self.info["played"] = time.time()
        tmp = self.info_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.info, indent=1))
        tmp.replace(self.info_path)

    @property
    def name(self):
        return self.info.get("name", self.dir.name)

    def card(self, who):
        return self.dir / f"{who}.mcd"

    @property
    def joint_save(self):
        return self.dir / "session.coop"

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
        return written

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
    return sum(p.savestates_size() for p in Playthrough.all())


class Moments:
    """Watches both games for moments worth a savestate (checked a few times a second)."""

    def __init__(self, playthrough):
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
