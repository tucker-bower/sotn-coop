"""Joint saves for couch and online co-op (design/M3-teleport-respawn-save.md, D31, D36, D74).

The launcher holds both games' mailboxes (couch) or one local mailbox plus a Host (online).
When either game saves at a save room, the other is asked to save too: its own game writes a
normal memory card save in the same block, resuming in the saver's save room (M3b, D46), so each
player can resume from the game's Load menu. Both saves also go into one session file, the backup
(and what "both players dead" reloads). Resuming, or both players dying, loads that file back
into both games.
"""

import base64
import struct
from pathlib import Path

from .mailbox import CMD_GAME_OVER, CMD_LOAD_SAVE, CMD_SAVE_NOW, DEAD, SAVE_DATA_SIZE

MAGIC, VERSION = b"COOPSAVE", 1
_INFO = 0x200                      # SaveData.info (include/game.h)
_STAGE, _ROOM_X, _ROOM_Y = 0x28, 0x2C, 0x2E  # within SaveInfo
BOTH_DEAD_FRAMES = 4               # ticks both must be waiting before the launcher acts


def save_room(blob):
    """(stage, roomX, roomY) a SaveData resumes in."""
    stage = struct.unpack_from("<h", blob, _INFO + _STAGE)[0]
    x, y = struct.unpack_from("<HH", blob, _INFO + _ROOM_X)
    return stage, x, y


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
        self.mb, self.path = mailboxes, Path(path)
        self.host, self.rank = host, rank
        self.seen = [m.save_seq() for m in mailboxes]
        self.pending = None   # (saver index / "local" / "remote", blob) while the partner saves
        self.dead_frames = 0
        self.saves = 0        # joint saves written
        self.resumed = False  # the session file was loaded in this run

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
                write_session(self.path, blobs)
                self.pending = None
                self.saves += 1
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
                remote_blob = self.pending[1]
                blobs = [blob, remote_blob] if self.rank == 0 else [remote_blob, blob]
                write_session(self.path, blobs)
                self.pending = None
                self.saves += 1
                self.host.send_control({"op": "save_done", "blob": base64.b64encode(blob).decode("ascii")})
            else:
                stage, x, y = save_room(blob)
                block = m.save_block()
                self.pending = ("local", blob)
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
                blobs = [local_blob, remote_blob] if self.rank == 0 else [remote_blob, local_blob]
                write_session(self.path, blobs)
                self.pending = None
                self.saves += 1
            elif op == "load_save":
                blobs = [base64.b64decode(b) for b in msg["blobs"]]
                write_session(self.path, blobs)
                self.resumed = True
                self.dead_frames = 0
                m.put_save(blobs[self.rank])
                m.command(CMD_LOAD_SAVE)
            elif op == "game_over":
                self.dead_frames = 0
                m.command(CMD_GAME_OVER)
        self._both_dead_online()

    def _both_dead_online(self):
        m = self.mb[0]
        both = bool(m.self_presence().flags & DEAD and m.partner_presence().flags & DEAD and m.partner_age() <= 30)
        if both:
            self.dead_frames += 1
        else:
            self.dead_frames = 0
        if self.dead_frames == BOTH_DEAD_FRAMES and self.rank == 0:
            if (self.saves or self.resumed) and self.path.exists():
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
            if (self.saves or self.resumed) and self.path.exists():
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
        blobs = read_session(self.path)
        if self.host is not None:
            self.mb[0].put_save(blobs[self.rank])
            self.mb[0].command(CMD_LOAD_SAVE)
            self.host.send_control({"op": "load_save", "blobs": [base64.b64encode(b).decode("ascii") for b in blobs]})
            return
        for m, blob in zip(self.mb, blobs):
            m.put_save(blob)
            m.command(CMD_LOAD_SAVE)
