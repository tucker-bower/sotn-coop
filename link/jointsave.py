"""Joint saves for couch co-op (design/M3-teleport-respawn-save.md, D31, D36).

The launcher holds both games' mailboxes. When either game saves at a save room, the other is
asked to save too: its own game writes a normal memory card save in the same block, resuming in
the saver's save room (M3b, D46), so each player can resume from the game's Load menu. Both saves
also go into one session file, the backup (and what "both players dead" reloads).
Resuming, or both players dying, loads that file back into both games.

`mailboxes` are link.mailbox.Mailbox objects, or anything with the same methods (the harness
passes proxies to its worker processes).
"""

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
    Path(path).write_bytes(MAGIC + struct.pack("<II", VERSION, len(blobs)) + b"".join(blobs))


def read_session(path):
    data = Path(path).read_bytes()
    assert data[:8] == MAGIC, f"{path} is not a co-op session"
    version, n = struct.unpack_from("<II", data, 8)
    assert version == VERSION
    return [data[16 + i * SAVE_DATA_SIZE:16 + (i + 1) * SAVE_DATA_SIZE] for i in range(n)]


class JointSave:
    def __init__(self, mailboxes, path):
        self.mb, self.path = mailboxes, Path(path)
        self.seen = [m.save_seq() for m in mailboxes]
        self.pending = None   # (saver index, saver's blob) while the partner saves
        self.dead_frames = 0
        self.saves = 0        # joint saves written

    def tick(self):
        """Once per frame, after both games' hosts."""
        for i, m in enumerate(self.mb):
            seq = m.save_seq()
            if seq == self.seen[i]:
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

    def _both_dead(self):
        if all(m.self_presence().flags & DEAD for m in self.mb):
            self.dead_frames += 1
        else:
            self.dead_frames = 0
        if self.dead_frames == BOTH_DEAD_FRAMES:
            if self.path.exists():
                self.resume()
            else:
                for m in self.mb:
                    m.command(CMD_GAME_OVER)

    def request(self, i, block=0):
        """Has player i save where it stands, to its card's `block`, as if at a save room (tests).
        The partner then saves too, through tick()."""
        p = self.mb[i].self_presence()
        self.mb[i].command(CMD_SAVE_NOW, p.stage, block, p.room_left, p.room_top)

    def resume(self):
        """Loads the session file into both games (from the title screen, or in play)."""
        for m, blob in zip(self.mb, read_session(self.path)):
            m.put_save(blob)
            m.command(CMD_LOAD_SAVE)
