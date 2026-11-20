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
import logging
import os
import struct
from pathlib import Path

from .mailbox import BUSY, CMD_ARRIVE, CMD_GAME_OVER, CMD_LOAD_SAVE, CMD_SAVE_NOW, CUTSCENE, DEAD, IN_PLAY, SAVE_DATA_SIZE

MAGIC, VERSION = b"COOPSAVE", 1
VERSION_IDS = 2  # 3+ players (M17): each slot's player id follows the slots
PID_SIZE = 16
_INFO = 0x200                      # SaveData.info (include/game.h)
_STAGE, _ROOM_X, _ROOM_Y = 0x28, 0x2C, 0x2E  # within SaveInfo
_NAME = 0x200                      # SaveInfo.name: 12 chars, typed at the game's name entry
_LEVEL, _EXP = 0x238 + 0x284, 0x238 + 0x288  # SaveData.status (PlayerStatus) .level, .exp
BOTH_DEAD_FRAMES = 4               # ticks both must be waiting before the launcher acts
LINKED_FRAMES = 600                # a partner heard from within 10 s (module: PartnerLinked)
PARTNER_SAVE_FRAMES = 300          # waiting this long for the partner's save: save alone
PARTNER_GONE_FRAMES = 300          # not heard from for this long: they've left
RESEND_LOAD_FRAMES = 300           # back, and out of play this long: they get the load again
ARRIVE_AFTER_FRAMES = 60           # in play this long after a load before a test castle's arrive


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


def both_slots(blobs, shared_level=True):
    """[slot 1, slot 2] to load: slot 2 a copy of slot 1 if it has none yet, both at the
    higher XP (unless the castle's rules give each player a level of their own: D162)."""
    blobs = [b for b in blobs if b is not None]
    if len(blobs) == 1:
        blobs = [blobs[0], blobs[0]]
    if not shared_level:
        return blobs
    exp = max(save_fields(b)[3] for b in blobs)
    return [with_exp(b, exp) for b in blobs]


def write_session(path, blobs, ids=None):
    """ids: each slot's player id (3+ players), or None (the two-player file, read by older versions)."""
    assert all(b is not None and len(b) == SAVE_DATA_SIZE for b in blobs)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Whole or not at all: written in place, a full disk left a cut-short save (#277)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tail = b"" if ids is None else b"".join((i or "").encode("ascii", "replace")[:PID_SIZE].ljust(PID_SIZE, b"\0")
                                                for i in ids)
        tmp.write_bytes(MAGIC + struct.pack("<II", VERSION if ids is None else VERSION_IDS, len(blobs)) +
                        b"".join(blobs) + tail)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_session(path):
    data = Path(path).read_bytes()
    assert data[:8] == MAGIC, f"{path} is not a co-op session"
    version, n = struct.unpack_from("<II", data, 8)
    assert version in (VERSION, VERSION_IDS)
    return [data[16 + i * SAVE_DATA_SIZE:16 + (i + 1) * SAVE_DATA_SIZE] for i in range(n)]


def read_ids(path):
    """Each slot's player id ("" where unknown), from a 3+ player file; None for a two-player one."""
    data = Path(path).read_bytes()
    version, n = struct.unpack_from("<II", data, 8)
    if version != VERSION_IDS:
        return None
    at = 16 + n * SAVE_DATA_SIZE
    return [data[at + i * PID_SIZE:at + (i + 1) * PID_SIZE].split(b"\0")[0].decode("ascii", "replace") for i in range(n)]


class JointSave:
    def __init__(self, mailboxes, path, host=None, rank=0):
        """path: the castle's joint save; None until it's known (an online joiner learns the
        host's castle in the lobby: launcher/app.py sets it)."""
        self.mb, self.path = mailboxes, (Path(path) if path else None)
        self.host, self.rank = host, rank
        self.on_write = None  # (blobs) -> None: the launcher updates the castle's info
        self.error = None     # the last joint save that couldn't be written (OSError), until shown
        self.shared_level = True  # the castle's rules (D162)
        self.seen = [m.save_seq() for m in mailboxes]
        self.pending = None   # (saver index / "local" / "remote", blob) while the partner saves
        self.dead_frames = 0
        self.saves = 0        # joint saves written
        self.resumed = False  # the session file was loaded in this run
        self.sent_load = False  # this game (the host) told the partner to load it
        self.partner_gone = False  # the link was lost since the partner was last in play
        self.partner_out = 0    # frames the partner has been out of play since coming back
        self._pending_frames = 0
        self.start = None     # (stage, room, x, y): a test castle's start, until its first save
        self._arrive = []     # [mailbox, frames in play since its save loaded, start]
        self.partner_crashed = False  # the partner's app said its game stopped (issue 113)
        self._load_msg = None  # the host's load, until this game is running: its boot wipes one written sooner (issue 61)
        self.room = None  # 3+ players (M17): harness.session.RoomProxy; then each partner by player number
        self.pid = None   # this player's lasting id: their slot follows it
        self._out = {}    # player 0: frames each partner has been heard but out of play

    def _write(self, blobs):
        """blobs: [slot 1 (this machine's player), slot 2 or None (keep the file's)]."""
        if self.path is None:
            return
        if blobs[1] is None:
            old = read_session(self.path) if self.path.exists() else []
            blobs = [blobs[0]] + old[1:2]
        try:
            write_session(self.path, blobs)
        except OSError as e:  # a full disk: the castle keeps its last save, and the player is told
            logging.getLogger("launcher").warning("joint save not written: %s", e)
            self.error = e
            return
        self.saves += 1
        self.start = None
        if self.on_write:
            self.on_write(blobs)

    def _tick_arrive(self):
        """After a load with a start: each game goes there once its save has loaded and it has
        been in play for a moment (an arrive during the load is lost)."""
        for a in list(self._arrive):
            q = a[0].self_presence()
            if q.flags & CUTSCENE:  # the start's scene: it's there. Sent after it, the fight was reloaded
                self._arrive.remove(a)  # and the scene played again (the Succubus's, playtest 0.14)
            elif not (q.flags & IN_PLAY) or q.flags & BUSY:
                a[1] = 0 if a[1] is None else a[1]  # loading: from here on, count
            elif a[1] is not None:
                a[1] += 1
                if a[1] >= ARRIVE_AFTER_FRAMES:
                    a[0].command(CMD_ARRIVE, *a[2])
                    self._arrive.remove(a)

    def tick(self):
        """Once per frame, after the game host(s)."""
        self._tick_arrive()
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

    def _bring_partner(self, m):
        """A partner who came back to a castle already under way sits at their title screen, and
        only a load brings them in (playtest 0.14). The host sends it again, once per return."""
        age = m.partner_age()
        if age > PARTNER_GONE_FRAMES:
            self.partner_gone = True
            self.partner_out = 0
            return
        if not self.partner_gone or not self.sent_load or age > 30 or self.path is None or not self.path.exists():
            return
        if m.partner_presence().flags & 1:
            self.partner_gone = False
            return
        self.partner_out += 1
        if self.partner_out >= RESEND_LOAD_FRAMES:
            self.partner_gone = False
            blobs = both_slots(read_session(self.path), self.shared_level)
            b64 = lambda b: base64.b64encode(b).decode("ascii")
            self.host.send_control({"op": "load_save", "yours": b64(blobs[1]), "mine": b64(blobs[0]), "start": None})

    def _tick_online(self):
        if self.room is not None:
            self._tick_room()
            return
        m = self.mb[0]
        self._bring_partner(m)
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
            elif op == "load_save":
                self._load_msg = msg
            elif op == "game_over":
                self.dead_frames = 0
                m.command(CMD_GAME_OVER)
            elif op == "crashed":
                self.partner_crashed = True
        if self._load_msg and m.ready() and m.self_presence().flags:  # its code is running: boot's over
            self._load(m, self._load_msg)
            self._load_msg = None
        if self.pending and self.pending[0] == "local":  # the partner never answered: alone
            self._pending_frames += 1
            if self._pending_frames > PARTNER_SAVE_FRAMES:
                self._write([self.pending[1], None])
                self.pending = None
        self._both_dead_online()

    def _load(self, m, msg):
        """The host's castle: "yours" is this player's slot."""
        yours, theirs = base64.b64decode(msg["yours"]), base64.b64decode(msg["mine"])
        if self.path is not None:
            try:
                write_session(self.path, [yours, theirs])
            except OSError as e:  # a full disk: the game loads it all the same
                logging.getLogger("launcher").warning("joiner's copy not written: %s", e)
                self.error = e
        self.resumed = True
        self.dead_frames = 0
        m.put_save(yours)
        m.command(CMD_LOAD_SAVE)
        # the host's test castle: arrive where it starts. A new load replaces any arrival
        # still waiting: the last one's sent a boss rush's joiner back to the boss before.
        self._arrive = [[m, None, tuple(msg["start"])]] if msg.get("start") else []

    def _both_dead_online(self):
        """Both players dead, or the host's player dead with no partner (a solo castle, or one
        the partner left): the castle's last save loads. Alone, the game's own Game Over led to
        its title and file select, which mean nothing in a castle (#240). With no save yet, it's
        the game's Game Over."""
        m = self.mb[0]
        dead = bool(m.self_presence().flags & DEAD)
        alone = m.partner_age() >= LINKED_FRAMES
        both = dead and (alone or bool(m.partner_presence().flags & DEAD and m.partner_age() <= 30))
        if both:
            self.dead_frames += 1
        else:
            self.dead_frames = 0
        if self.dead_frames == BOTH_DEAD_FRAMES and self.rank == 0:
            if (self.saves or self.resumed) and self.path and self.path.exists():
                self.resume()
            elif not alone:
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
        self.sent_load = True
        blobs = both_slots(read_session(self.path), self.shared_level)
        self._arrive = [[m, None, tuple(self.start)] for m in self.mb] if self.start else []
        if self.room is not None:
            self.mb[0].put_save(blobs[0])
            self.mb[0].command(CMD_LOAD_SAVE)
            for n, p in self.room.players().items():
                self._load_for(n, p, list(self.start) if self.start else None)
            return
        if self.host is not None:
            self.mb[0].put_save(blobs[0])
            self.mb[0].command(CMD_LOAD_SAVE)
            b64 = lambda b: base64.b64encode(b).decode("ascii")
            self.host.send_control({"op": "load_save", "yours": b64(blobs[1]), "mine": b64(blobs[0]),
                                    "start": list(self.start) if self.start else None})
            return
        for m, blob in zip(self.mb, blobs):
            m.put_save(blob)
            m.command(CMD_LOAD_SAVE)

    # --- 3+ players (M17 step 6): every partner by player number; slots follow player ids

    def _slots(self):
        """{player id: blob} of the castle's file (slot 1 is this player's, whatever its id)."""
        if self.path is None or not self.path.exists():
            return {}
        blobs, ids = read_session(self.path), read_ids(self.path)
        if ids is None:  # a two-player castle: slot 1 is ours, slot 2 the partner's, id unknown
            ids = [self.pid or "me", "partner"][:len(blobs)]
        ids[0] = self.pid or ids[0] or "me"
        return dict(zip(ids, blobs))

    def _write_ids(self, new):
        """Writes the castle's file with these players' saves ({player id: blob}) over what it had."""
        if self.path is None:
            return
        slots = self._slots()
        slots.update(new)
        me = self.pid or "me"
        order = [me] + [i for i in slots if i != me]
        if me not in slots:
            return
        blobs = [slots[i] for i in order]
        try:
            write_session(self.path, blobs, order)
        except OSError as e:
            logging.getLogger("launcher").warning("joint save not written: %s", e)
            self.error = e
            return
        self.saves += 1
        if self.on_write:
            self.on_write(blobs[:2])

    def _load_for(self, n, info, start=None):
        """Player 0: player n's castle load: their own slot, or a copy of ours for a new player."""
        slots = self._slots()
        mine = slots.get(self.pid or "me")
        if mine is None:
            return
        yours = slots.get(info.get("pid")) or mine
        if self.shared_level:
            yours, mine = both_slots([yours, mine])
        b64 = lambda b: base64.b64encode(b).decode("ascii")
        self.room.send({"op": "load_save", "yours": b64(yours), "mine": b64(mine), "start": start}, to=n)

    def _tick_room(self):
        m = self.mb[0]
        players = self.room.players()
        linked = {n for n, p in players.items() if m.partner_age(p["slot"]) < LINKED_FRAMES}
        if self.rank == 0 and self.path is not None and self.path.exists():  # a player dropped in, or came back: their load
            for n, p in players.items():
                here = m.partner_age(p["slot"]) <= 30
                out = here and not m.partner_presence(p["slot"]).flags & IN_PLAY
                self._out[n] = self._out.get(n, 0) + 1 if out else 0
                if self._out[n] == RESEND_LOAD_FRAMES:
                    me = m.self_presence()  # where they arrive: beside this player
                    self._load_for(n, p, [me.stage, me.room_id, me.ground_x, me.ground_y] if me.flags & IN_PLAY else None)
        seq = m.save_seq()
        if seq < self.seen[0]:
            self.seen[0] = seq
        elif seq > self.seen[0]:
            self.seen[0] = seq
            blob = m.save_out()
            me = self.pid or "me"
            if self.pending and self.pending[0] == "remote":
                n, theirs = self.pending[1], self.pending[2]
                self._write_ids({me: blob, (players.get(n) or {}).get("pid") or f"player{n}": theirs})
                self.pending = None
                self.room.send({"op": "save_done", "blob": base64.b64encode(blob).decode("ascii")}, to=n)
            elif not linked:
                self._write_ids({me: blob})
            else:
                stage, x, y = save_room(blob)
                self.pending = ("local", blob, set(linked), {})
                self._pending_frames = 0
                self.room.send({"op": "save_req", "stage": stage, "block": m.save_block(), "x": x, "y": y,
                                "blob": base64.b64encode(blob).decode("ascii")})
        for n, msg in self.room.take():
            op = msg.get("op")
            pid = (players.get(n) or {}).get("pid") or f"player{n}"
            if op == "save_req":
                self.pending = ("remote", n, base64.b64decode(msg["blob"]))
                m.command(CMD_SAVE_NOW, msg["stage"], msg["block"], msg["x"], msg["y"])
            elif op == "save_done" and self.pending and self.pending[0] == "local":
                self.pending[3][pid] = base64.b64decode(msg["blob"])
                self.pending[2].discard(n)
                if not self.pending[2]:
                    self._write_ids({self.pid or "me": self.pending[1], **self.pending[3]})
                    self.pending = None
            elif op == "load_save":
                self._load_msg = msg
            elif op == "game_over":
                self.dead_frames = 0
                m.command(CMD_GAME_OVER)
            elif op == "crashed":
                self.partner_crashed = True
        if self._load_msg and m.ready() and m.self_presence().flags:
            msg, self._load_msg = self._load_msg, None
            self._load(m, msg)
            if self.pid and self.path is not None:  # our copy, with ids: slot 1 ours
                try:
                    write_session(self.path, [base64.b64decode(msg["yours"]), base64.b64decode(msg["mine"])],
                                  [self.pid, "host"])
                except OSError:
                    pass
        if self.pending and self.pending[0] == "local":  # someone never answered: what we have
            self._pending_frames += 1
            if self._pending_frames > PARTNER_SAVE_FRAMES:
                self._write_ids({self.pid or "me": self.pending[1], **self.pending[3]})
                self.pending = None
        self._both_dead_room(m, players, linked)

    def _both_dead_room(self, m, players, linked):
        """Everyone dead (or this player alone and dead): the castle's last save, for all."""
        dead = bool(m.self_presence().flags & DEAD)
        everyone = dead and all(m.partner_presence(players[n]["slot"]).flags & DEAD for n in linked)
        self.dead_frames = self.dead_frames + 1 if everyone else 0
        if self.dead_frames == BOTH_DEAD_FRAMES and self.rank == 0:
            if (self.saves or self.resumed) and self.path and self.path.exists():
                self.resume()
            elif linked:
                m.command(CMD_GAME_OVER)
                self.room.send({"op": "game_over"})
