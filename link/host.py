"""One host per game. Call after_frame() once per emulated frame, while the emulator is paused."""

import base64
import collections
import json
import zlib
import os
import struct
import time

from .mailbox import CHAR_BLOB_ADDR, EVENT_SIZE, Presence
from .playout import Playout
from .transport import (TAG_ACK, TAG_BYE, TAG_PRIM, TAG_SPRT, TAG_CACK, TAG_CTRL, TAG_EVENTS, TAG_HELLO, TAG_PRESENCE, TAG_SNAP,
                        WIRE_VERSION, ReliableChannel, ReliableMessages)

HELLO_EVERY = 60  # frames
STATUS_EVERY = 10  # frames: the most often this player's status is sent (M13)


def _presence(payload):
    """A partner's presence, and its buttons after it (M13; 0 from an older partner)."""
    p = Presence.unpack(payload)
    if len(payload) >= Presence.SIZE + 2:
        p.pad = struct.unpack_from("<H", payload, Presence.SIZE)[0]
    return p


class Host:
    def __init__(self, mailbox, transport, rank=0, patch_crc=None, playout=False):
        """rank: 0 or 1, distinct per game; breaks shared-room authority ties (design/M4).
        patch_crc: the co-op disc's (the patch's target CRC32): partners must match.
        playout: play the partner's state back at an even pace (link/playout.py): online, where
        the network bunches it up. Two games on one PC don't need it."""
        self.mailbox, self.transport, self.rank = mailbox, transport, rank
        self._snap_sent = 0
        self._snap_seq = 0
        self.events = ReliableChannel(transport, EVENT_SIZE)
        self.ctrl = ReliableMessages(transport)
        self._ctrl_inbox = []  # decoded JSON control messages (online joint saves)
        self._inbox = []       # partner events the game's in ring had no room for yet
        self._latest_seq = 0
        self.sent = self.received = 0
        self.events_sent = self.events_received = 0
        # The last minute of link traffic, for bug reports (F9): (time, way, what)
        self.log = collections.deque(maxlen=20000)
        # The handshake (docs/link-protocol.md): a partner with another link version or another
        # co-op disc is refused, and nothing is relayed (the games play on alone).
        # sid: this run of the host. A partner whose sid changes restarted: start afresh with it.
        self.hello = {"link": WIRE_VERSION, "patch": patch_crc, "sid": os.urandom(4).hex()}
        self.partner_hello = None
        self.playout = Playout() if playout else None
        self.restarts = 0
        self.connector = None  # finding the partner from a room code (link/connect.py)
        self.mismatch = None  # why the partner was refused, in words
        self.partner_left = False  # the partner said goodbye (its app closed or went back to its menu)
        self._sprites_sent, self._sprites_seq = False, 0  # sprites.c (M12)
        self._prims_sent, self._prims_seq = False, 0
        self._weapons_sent = [None, None]  # each hand's weapon copy last sent (module/weapons.c)
        self._familiar_sent = None  # the familiar copy last sent (module/familiar.c)
        self._status_sent, self._status_at = None, -STATUS_EVERY  # M13: this player's status, for the partner's body
        self._frames = 0
        self.character, self.options = 0, 0  # this game's player (design/M8): CHAR_*, OPT_*
        self.blob = None  # a character's CharBlob for this game's 8MB RAM (launcher/characters.py)

    def set_player(self, character=None, options=None, blob=None):
        """This game's player: CHAR_* (the game switches at its next load) and OPT_* settings.
        Written into the game every frame, so loading a savestate can't undo them. blob: Maria's
        overlay and voice (every game where someone plays her gets it: the partner's puppet
        draws from it too); rewritten whenever the game's copy isn't there."""
        if character is not None:
            self.character = character
        if options is not None:
            self.options = options
        if blob is not None:
            self.blob = blob
            self._put_blob()

    def _put_blob(self):
        adapter = self.mailbox.adapter
        if self.blob and adapter.read_bytes(CHAR_BLOB_ADDR, 32) != self.blob[:32]:
            adapter.write_bytes(CHAR_BLOB_ADDR, self.blob)

    def _note(self, way, what):
        self.log.append((time.monotonic(), way, what))

    def log_dump(self, seconds=60):
        """The last `seconds` of link traffic: [(seconds ago, "out"/"in", what)]."""
        now = time.monotonic()
        return [(round(now - t, 3), way, what) for t, way, what in self.log if now - t <= seconds]

    def set_hello(self, patch_crc=None, link_version=None):
        if patch_crc is not None:
            self.hello["patch"] = patch_crc
        if link_version is not None:
            self.hello["link"] = link_version
        return self.hello

    def set_castle(self, meta):
        """The castle this host plays (design/M11: {"id", "name", "created"}), told to the
        partner in every HELO: the joiner keeps a copy of it."""
        self.hello["castle"] = meta
        return True

    def start_connect(self, room, role, relay=None, **kw):
        """Find the partner for a room code (role "host" or "join"): link/connect.py."""
        from .connect import Connector, default_relay, room_token
        self.hello["room"] = room_token(room)
        self.transport.learn_peer = True
        version = {"link": self.hello.get("link"), "app": kw.pop("app", None)}
        self.connector = Connector(self.transport, room, role, relay or default_relay(), self._hello_bytes,
                                   version=version, **kw)
        return True

    def connect_status(self):
        return self.connector.status() if self.connector else None

    def set_playout(self, on=True):
        self.playout = Playout() if on else None
        return True

    def _partner_restarted(self):
        """The partner's host is a new one (it restarted): numbering starts again both ways."""
        self.restarts += 1
        self.partner_left = False  # back again
        self._sprites_seq = self._prims_seq = 0
        self._weapons_sent = [None, None]
        self._familiar_sent = None
        self._status_sent = None
        self.events = ReliableChannel(self.transport, EVENT_SIZE)
        self.ctrl = ReliableMessages(self.transport)
        self._inbox = []
        self._latest_seq = self._snap_seq = 0
        t = self.transport
        t._snap_done, t._snap_parts, t._got_snaps = 0, {}, type(t._got_snaps)()
        t._snap_acked, t._sent_snaps = 0, type(t._sent_snaps)()
        t._pres_frames, t._heard_ms, t._heard_at = [], 0, None
        if self.playout:
            self.playout.reset()

    def status(self):
        """Connection and handshake status for the launcher UI and tests."""
        age = None if self.transport.last_rx_time is None else round(self.transport.clock() - self.transport.last_rx_time, 2)
        return {
            **self.transport.quality(),
            "playout": self.playout.stats() if self.playout else None,
            "restarts": self.restarts,
            "rank": self.rank,
            "peer": self.transport.peer,
            "partner_hello": self.partner_hello,
            "mismatch": self.mismatch,
            "partner_left": self.partner_left,
            "rx_age": age,
            "sent": self.sent,
            "received": self.received,
        }

    def send_control(self, msg):
        """Sends a reliable control/save JSON dict to the partner host (online joint saves)."""
        self.ctrl.send(json.dumps(msg).encode())
        self._note("out", f"ctrl {msg.get('op')}")

    def _send_weapons(self):
        """A hand's weapon copy (overlay, tile sheet, palettes: module/weapons.c), once per new
        copy, so the partner can draw its swings. Reliable: it's sent rarely, and a lost one would
        leave the swings undrawn."""
        if not self.partner_hello:
            return
        for hand in (0, 1):
            ok, seq = self.mailbox.self_weapon_seq(hand)
            if ok and seq != self._weapons_sent[hand]:
                self._weapons_sent[hand] = seq
                blob = zlib.compress(self.mailbox.self_weapon(hand), 6)
                self.send_control({"op": "weapon", "hand": hand, "data": base64.b64encode(blob).decode("ascii")})

    def _send_familiar(self):
        """This player's familiar (overlay, tile sheet, palettes: module/familiar.c), once per new
        copy, for the partner to draw it. Reliable, as the weapons."""
        if not self.partner_hello:
            return
        ok, seq = self.mailbox.self_familiar_seq()
        if ok and seq != self._familiar_sent:
            self._familiar_sent = seq
            blob = zlib.compress(self.mailbox.self_familiar(), 6)
            self.send_control({"op": "familiar", "data": base64.b64encode(blob).decode("ascii")})

    def _take_familiar(self, msg):
        try:
            blob = zlib.decompress(base64.b64decode(msg["data"]))
        except (KeyError, TypeError, ValueError, zlib.error):
            return
        self.mailbox.write_partner_familiar(blob)

    def _send_status(self):
        """This player's status (stats, level, equipment: M13's partner body, module/partner.c)
        when it changes, at most every STATUS_EVERY frames. Reliable: the last one must arrive."""
        if not self.partner_hello or self._frames - self._status_at < STATUS_EVERY:
            return
        blob = self.mailbox.self_status()
        if blob != self._status_sent:
            self._status_sent, self._status_at = blob, self._frames
            self.send_control({"op": "status", "data": base64.b64encode(blob).decode("ascii")})

    def _take_weapon(self, msg):
        try:
            hand, blob = int(msg["hand"]) & 1, zlib.decompress(base64.b64decode(msg["data"]))
        except (KeyError, TypeError, ValueError, zlib.error):
            return
        self.mailbox.write_partner_weapon(hand, blob)

    def goodbye(self):
        """Tells the partner this game is leaving, so it can say so at once instead of waiting
        for silence (playtest 2026-10-25). Unacknowledged: sent a few times, as the app is closing."""
        if self.partner_hello and not self.mismatch:
            for _ in range(3):
                self.transport.send(TAG_BYE, json.dumps({"sid": self.hello["sid"]}).encode())
            self._note("out", "bye")

    def _check_bye(self, payload):
        try:
            sid = json.loads(payload).get("sid")
        except (ValueError, AttributeError):
            return
        if self.partner_hello and sid == self.partner_hello.get("sid") and not self.partner_left:
            self.partner_left = True
            self._note("in", "bye")

    def take_control(self):
        """Returns and clears received control/save JSON dicts."""
        out = list(self._ctrl_inbox)
        self._ctrl_inbox.clear()
        return out

    def _check_hello(self, payload, addr=None):
        try:
            theirs = json.loads(payload)
        except ValueError:
            return
        if self.hello.get("room") and theirs.get("room") != self.hello["room"]:
            # Someone in another room: not our partner. No room at all is a partner who typed our
            # ip:port (the fallback when room codes can't connect: design/M7b, M9), so only a host
            # takes one: a joiner with a room code would take any game on the network that answers
            # its LAN broadcast (an ip:port game in the same house; the harness's games, D100).
            if theirs.get("room") is not None or not self.connector or self.connector.role != "host":
                return
        if theirs.get("sid") == self.hello["sid"]:
            return  # our own HELO, come back to us (a candidate that was this PC, or a LAN broadcast)
        if (not self.hello.get("room") and theirs.get("room") and self.transport.peer
                and addr is not None and tuple(addr) != tuple(self.transport.peer)):
            return  # joined by ip:port: another room's LAN broadcast (link/connect.py) isn't our partner
        clock = theirs.pop("clock", None)
        if isinstance(clock, list) and len(clock) == 3:
            self.transport.clock_heard(*clock)
        if addr is not None and self.transport.learn_peer:
            self.transport.accept_peer(addr)
        if self.partner_hello and theirs.get("sid") != self.partner_hello.get("sid"):
            self._partner_restarted()
        self.partner_hello = theirs
        if theirs.get("link") != self.hello["link"]:
            self.mismatch = (f"Your partner's co-op version is different (link {theirs.get('link')}, "
                             f"yours {self.hello['link']}): both need the same version.")
        elif theirs.get("patch") and self.hello["patch"] and theirs["patch"] != self.hello["patch"]:
            self.mismatch = "Your partner's co-op disc is a different version: both need the same."
        else:
            self.mismatch = None

    def _hello_bytes(self):
        """HELO, with the clock stamps that measure the round trip before the games run."""
        return json.dumps(dict(self.hello, clock=list(self.transport.clock_stamp()))).encode()

    def handshake_tick(self):
        """Exchanges HELO before emulation starts (online connection lobby)."""
        if self._frames % 15 == 0:
            self.transport.send(TAG_HELLO, self._hello_bytes())
        self._frames += 1
        if self.connector:
            self.connector.tick()
        for tag, _, _, payload, addr in self.transport.receive():
            if tag == TAG_HELLO:
                self._check_hello(payload, addr)
            elif tag == TAG_BYE:
                self._check_bye(payload)
        return self.status()

    def after_frame(self):
        self.transport.frame += 1
        self._put_blob()
        if self.connector and self.connector.state not in ("connected", "failed"):
            self.connector.tick()
        if self._frames % HELLO_EVERY == 0:
            self.transport.send(TAG_HELLO, self._hello_bytes())
        self._frames += 1
        if not self.mailbox.ready():  # the game is booting: only the handshake (and the ping)
            for tag, _, _, payload, addr in self.transport.receive():
                if tag == TAG_HELLO:
                    self._check_hello(payload, addr)
                elif tag == TAG_BYE:
                    self._check_bye(payload)
            return
        if self.mismatch:  # refused: still say hello (the partner may update), relay nothing
            for tag, _, _, payload, addr in self.transport.receive():
                if tag == TAG_HELLO:
                    self._check_hello(payload, addr)
                elif tag == TAG_BYE:
                    self._check_bye(payload)
            return
        self.mailbox.set_rank(self.rank)
        self.mailbox.set_character(self.character)
        self.mailbox.set_options(self.options)
        me = self.mailbox.self_presence()
        self.transport.send(TAG_PRESENCE, me.pack() + struct.pack("<H", me.pad & 0xFFFF))
        sprites = self.mailbox.self_sprites()
        if sprites or self._sprites_sent:  # one empty message after the last, to clear them
            self.transport.send(TAG_SPRT, sprites)
        self._sprites_sent = bool(sprites)
        prims = self.mailbox.self_prims()
        if prims or self._prims_sent:
            self.transport.send(TAG_PRIM, zlib.compress(prims, 1))
        self._prims_sent = bool(prims)
        self._send_weapons()
        self._send_familiar()
        self._send_status()
        seq, snap = self.mailbox.snapshot_out()
        if seq != self._snap_sent:
            self._snap_sent = seq
            self.transport.send(TAG_SNAP, snap)
            self._note("out", f"snapshot {seq} ({len(snap)} bytes)")
        self.sent += 1
        mine = self.mailbox.take_events()
        self.events.queue(mine)
        self.events_sent += len(mine)
        for ev in mine:
            self._note("out", "event %d a=%#x b=%#x" % struct.unpack("<BxHI", ev[:8]))

        latest, reliable, ctrl_dgrams, snap, sprites, prims_in = None, [], [], None, None, None
        now = self.transport.clock()
        for dgram in self.transport.receive():
            tag, seq, frame, payload, addr = dgram
            if tag == TAG_PRESENCE:
                if self.playout:
                    self.playout.push_presence(now, frame, _presence(payload))
                elif seq > self._latest_seq:  # UDP may reorder: keep the newest
                    self._latest_seq, latest = seq, _presence(payload)
            elif tag == TAG_SNAP:
                if self.playout:
                    self.playout.push_snapshot(now, frame, payload)
                elif seq > self._snap_seq:
                    self._snap_seq, snap = seq, payload
            elif tag in (TAG_EVENTS, TAG_ACK):
                reliable.append(dgram)
            elif tag in (TAG_CTRL, TAG_CACK):
                ctrl_dgrams.append(dgram)
            elif tag == TAG_PRIM:
                if seq > self._prims_seq:
                    self._prims_seq, prims_in = seq, payload
            elif tag == TAG_SPRT:
                if seq > self._sprites_seq:  # the newest only
                    self._sprites_seq, sprites = seq, payload
            elif tag == TAG_BYE:
                self._check_bye(payload)
            elif tag == TAG_HELLO:
                self._check_hello(payload, addr)
                if self.mismatch:
                    return
        if self.playout:
            loss = self.transport.quality()["loss_pct"]
            self.playout.min_delay = 1 / 60 if loss else 0.0
            latest, snap = self.playout.pop(now)
        if latest is not None:
            self.mailbox.write_partner(latest)
            self.received += 1
        if sprites is not None:
            self.mailbox.write_partner_sprites(sprites)
        if prims_in is not None:
            try:
                self.mailbox.write_partner_prims(zlib.decompress(prims_in))
            except zlib.error:
                pass
        if snap is not None:
            self.mailbox.put_snapshot(snap)
            self._note("in", f"snapshot ({len(snap)} bytes)")
        theirs = self.events.tick(reliable)
        for ev in theirs:
            self._note("in", "event %d a=%#x b=%#x" % struct.unpack("<BxHI", ev[:8]))
        self.events_received += len(theirs)
        self._inbox += theirs
        if self._inbox:
            n = self.mailbox.give_events(self._inbox)
            self._inbox = self._inbox[n:]
        if ctrl_dgrams or self.ctrl.unacked:
            for raw_msg in self.ctrl.tick(ctrl_dgrams):
                try:
                    msg = json.loads(raw_msg)
                    self._note("in", f"ctrl {msg.get('op')}")
                    if msg.get("op") == "weapon":
                        self._take_weapon(msg)
                    elif msg.get("op") == "familiar":
                        self._take_familiar(msg)
                    elif msg.get("op") == "status":
                        try:
                            self.mailbox.write_partner_status(base64.b64decode(msg["data"]))
                        except (KeyError, TypeError, ValueError):
                            pass
                    else:
                        self._ctrl_inbox.append(msg)
                except ValueError:
                    pass
