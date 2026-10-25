"""Joint saves for couch and online co-op (design/M3-teleport-respawn-save.md, D31, D36, D74).

The launcher holds both games' mailboxes (couch) or one local mailbox plus a Host (online).
When either game saves at a save room, the other is asked to save too: its own game writes a
normal memory card save in the same block, resuming in the saver's save room (M3b, D46), so each
player can resume from the game's Load menu. Both saves also go into one session file, the backup
(and what "both players dead" reloads). Resuming, or both players dying, loads that file back
into both games.

Castles (design/M11): the file's slot 1 is always this machine's player and slot 2 whoever
plays with them, on every machine (an online joiner's copy too). A save made with no partner
(solo, or the partner gone) writes slot 1 and keeps slot 2. A castle with no slot 2 yet gives
the partner a copy of slot 1. Loading gives both the higher XP (one shared level).
"""

import base64
import struct
from pathlib import Path

from .mailbox import CMD_GAME_OVER, CMD_LOAD_SAVE, CMD_SAVE_NOW, DEAD, SAVE_DATA_SIZE

MAGIC, VERSION = b"COOPSAVE", 1
_INFO = 0x200                      # SaveData.info (include/game.h)
_STAGE, _ROOM_X, _ROOM_Y = 0x28, 0x2C, 0x2E  # within SaveInfo
_NAME = 0x200                      # SaveInfo.name: 12 chars, typed at the game's name entry
_LEVEL, _EXP = 0x238 + 0x284, 0x238 + 0x288  # SaveData.status (PlayerStatus) .level, .exp
BOTH_DEAD_FRAMES = 4               # ticks both must be waiting before the launcher acts
LINKED_FRAMES = 600                # a partner heard from within 10 s (module: PartnerLinked)
PARTNER_SAVE_FRAMES = 300          # waiting this long for the partner's save: save alone


def save_room(blob):
    """(stage, roomX, roomY) a SaveData resumes in."""
    stage = struct.unpack_from("<h", blob, _INFO + _STAGE)[0]
    x, y = struct.unpack_from("<HH", blob, _INFO + _ROOM_X)
    return stage, x, y


def save_fields(blob):
    """(typed name, stage, level, exp) of a SaveData."""
    raw = blob[_NAME:_NAME + 12].split(b"\0")[0]
    name = "".join(chr(c) for c in raw if 32 <= c < 127).strip()
    stage = struct.unpack_from("<h", blob, _INFO + _STAGE)[0]
    level, exp = struct.unpack_from("<II", blob, _LEVEL)
    return name, stage, level, exp


def with_exp(blob, exp):
    """blob with its XP raised to exp: its game levels up to match, the normal way, in play."""
    if struct.unpack_from("<I", blob, _EXP)[0] >= exp:
        return blob
    out = bytearray(blob)
    struct.pack_into("<I", out, _EXP, exp)
    return bytes(out)


def both_slots(blobs):
    """[slot 1, slot 2] to load: slot 2 a copy of slot 1 if it has none yet, both at the
    higher XP."""
    blobs = [b for b in blobs if b is not None]
    if len(blobs) == 1:
        blobs = [blobs[0], blobs[0]]
    exp = max(save_fields(b)[3] for b in blobs)
    return [with_exp(b, exp) for b in blobs]


def write_session(path, blobs):
    assert all(b is not None and len(b) == SAVE_DATA_SIZE for b in blobs)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(MAGIC + struct.pack("<II", VERSION, len(blobs)) + b"".join(blobs))


def read_session(path):
    data = Path(path).read_bytes()
    assert data[:8] == MAGIC, f"{path} is not a co-op session"
    version, n = struct.unpack_from("<II", data, 8)
    assert version == VERSION
    return [data[16 + i * SAVE_DATA_SIZE:16 + (i + 1) * SAVE_DATA_SIZE] for i in range(n)]


class JointSave:
    def __init__(self, mailboxes, path, host=None, rank=0):
        """path: the castle's joint save; None until it's known (an online joiner learns the
        host's castle in the lobby: launcher/app.py sets it)."""
        self.mb, self.path = mailboxes, (Path(path) if path else None)
        self.host, self.rank = host, rank
        self.on_write = None  # (blobs) -> None: the launcher updates the castle's info
        self.seen = [m.save_seq() for m in mailboxes]
        self.pending = None   # (saver index / "local" / "remote", blob) while the partner saves
        self.dead_frames = 0
        self.saves = 0        # joint saves written
        self.resumed = False  # the session file was loaded in this run
        self._pending_frames = 0

    def _write(self, blobs):
        """blobs: [slot 1 (this machine's player), slot 2 or None (keep the file's)]."""
        if self.path is None:
            return
        if blobs[1] is None:
            old = read_session(self.path) if self.path.exists() else []
            blobs = [blobs[0]] + old[1:2]
        write_session(self.path, blobs)
        self.saves += 1
        if self.on_write:
            self.on_write(blobs)

    def tick(self):
        """Once per frame, after the game host(s)."""
        if self.host is not None:
            self._tick_online()
            return
        for i, m in enumerate(self.mb):
            seq = m.save_seq()
            if seq <= self.seen[i]:
                self.seen[i] = seq
                continue
            self.seen[i] = seq
            blob = m.save_out()
            if self.pending and self.pending[0] != i:  # the partner's save, answering ours
                blobs = [None] * len(self.mb)
                blobs[self.pending[0]], blobs[i] = self.pending[1], blob
                self._write(blobs)
                self.pending = None
            else:                                        # a player saved at a save room
                stage, x, y = save_room(blob)
                block = m.save_block()
                for j, other in enumerate(self.mb):
                    if j != i:
                        other.command(CMD_SAVE_NOW, stage, block, x, y)
                self.pending = (i, blob)
        self._both_dead()

    def _tick_online(self):
        m = self.mb[0]
        seq = m.save_seq()
        if seq < self.seen[0]:
            self.seen[0] = seq
        elif seq > self.seen[0]:
            self.seen[0] = seq
            blob = m.save_out()
            if self.pending and self.pending[0] == "remote":
                self._write([blob, self.pending[1]])
                self.pending = None
                self.host.send_control({"op": "save_done", "blob": base64.b64encode(blob).decode("ascii")})
            elif m.partner_age() >= LINKED_FRAMES:  # solo, or the partner's gone: slot 1 alone
                self._write([blob, None])
            else:
                stage, x, y = save_room(blob)
                block = m.save_block()
                self.pending = ("local", blob)
                self._pending_frames = 0
                self.host.send_control({
                    "op": "save_req", "stage": stage, "block": block, "x": x, "y": y,
                    "blob": base64.b64encode(blob).decode("ascii"),
                })
        for msg in self.host.take_control():
            op = msg.get("op")
            if op == "save_req":
                remote_blob = base64.b64decode(msg["blob"])
                self.pending = ("remote", remote_blob)
                m.command(CMD_SAVE_NOW, msg["stage"], msg["block"], msg["x"], msg["y"])
            elif op == "save_done":
                remote_blob = base64.b64decode(msg["blob"])
                local_blob = self.pending[1] if (self.pending and self.pending[0] == "local") else m.save_out()
                self._write([local_blob, remote_blob])
                self.pending = None
            elif op == "load_save":  # the host's castle: "yours" is this player's slot
                yours, theirs = base64.b64decode(msg["yours"]), base64.b64decode(msg["mine"])
                if self.path is not None:
                    write_session(self.path, [yours, theirs])
                self.resumed = True
                self.dead_frames = 0
                m.put_save(yours)
                m.command(CMD_LOAD_SAVE)
            elif op == "game_over":
                self.dead_frames = 0
                m.command(CMD_GAME_OVER)
        if self.pending and self.pending[0] == "local":  # the partner never answered: alone
            self._pending_frames += 1
            if self._pending_frames > PARTNER_SAVE_FRAMES:
                self._write([self.pending[1], None])
                self.pending = None
        self._both_dead_online()

    def _both_dead_online(self):
        m = self.mb[0]
        both = bool(m.self_presence().flags & DEAD and m.partner_presence().flags & DEAD and m.partner_age() <= 30)
        if both:
            self.dead_frames += 1
        else:
            self.dead_frames = 0
        if self.dead_frames == BOTH_DEAD_FRAMES and self.rank == 0:
            if (self.saves or self.resumed) and self.path and self.path.exists():
                self.resume()
            else:
                m.command(CMD_GAME_OVER)
                self.host.send_control({"op": "game_over"})

    def _both_dead(self):
        if all(m.self_presence().flags & DEAD for m in self.mb):
            self.dead_frames += 1
        else:
            self.dead_frames = 0
        if self.dead_frames == BOTH_DEAD_FRAMES:
            # Only a joint save made during this run: an older file may be from another
            # playthrough (playtest 1: the end of the prologue loaded a save-room test's save).
            if (self.saves or self.resumed) and self.path and self.path.exists():
                self.resume()
            else:
                for m in self.mb:
                    m.command(CMD_GAME_OVER)

    def request(self, i=0, block=0):
        """Has player i save where it stands, to its card's `block`, as if at a save room (tests).
        The partner then saves too, through tick()."""
        p = self.mb[i].self_presence()
        self.mb[i].command(CMD_SAVE_NOW, p.stage, block, p.room_left, p.room_top)

    def resume(self):
        """Loads the session file into both games (from the title screen, or in play)."""
        self.resumed = True
        blobs = both_slots(read_session(self.path))
        if self.host is not None:
            self.mb[0].put_save(blobs[0])
            self.mb[0].command(CMD_LOAD_SAVE)
            b64 = lambda b: base64.b64encode(b).decode("ascii")
            self.host.send_control({"op": "load_save", "yours": b64(blobs[1]), "mine": b64(blobs[0])})
            return
        for m, blob in zip(self.mb, blobs):
            m.put_save(blob)
            m.command(CMD_LOAD_SAVE)
