"""One host per game. Call after_frame() once per emulated frame, while the emulator is paused."""

import collections
import json
import os
import struct
import time

from .mailbox import CHAR_BLOB_ADDR, EVENT_SIZE, Presence
from .playout import Playout
from .transport import (TAG_ACK, TAG_CACK, TAG_CTRL, TAG_EVENTS, TAG_HELLO, TAG_PRESENCE, TAG_SNAP,
                        WIRE_VERSION, ReliableChannel, ReliableMessages)

HELLO_EVERY = 60  # frames


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
            "rx_age": age,
            "sent": self.sent,
            "received": self.received,
        }

    def send_control(self, msg):
        """Sends a reliable control/save JSON dict to the partner host (online joint saves)."""
        self.ctrl.send(json.dumps(msg).encode())
        self._note("out", f"ctrl {msg.get('op')}")

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
        if self.hello.get("room") and theirs.get("room") not in (None, self.hello["room"]):
            return  # someone in another room: not our partner. (No room at all: a partner who
            # typed our ip:port, the fallback when room codes can't connect: design/M7b, M9.)
        if theirs.get("sid") == self.hello["sid"]:
            return  # our own HELO, come back to us (a candidate that was this PC)
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
            return
        if self.mismatch:  # refused: still say hello (the partner may update), relay nothing
            for tag, _, _, payload, addr in self.transport.receive():
                if tag == TAG_HELLO:
                    self._check_hello(payload, addr)
            return
        self.mailbox.set_rank(self.rank)
        self.mailbox.set_character(self.character)
        self.mailbox.set_options(self.options)
        self.transport.send(TAG_PRESENCE, self.mailbox.self_presence().pack())
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

        latest, reliable, ctrl_dgrams, snap = None, [], [], None
        now = self.transport.clock()
        for dgram in self.transport.receive():
            tag, seq, frame, payload, addr = dgram
            if tag == TAG_PRESENCE:
                if self.playout:
                    self.playout.push_presence(now, frame, Presence.unpack(payload))
                elif seq > self._latest_seq:  # UDP may reorder: keep the newest
                    self._latest_seq, latest = seq, Presence.unpack(payload)
            elif tag == TAG_SNAP:
                if self.playout:
                    self.playout.push_snapshot(now, frame, payload)
                elif seq > self._snap_seq:
                    self._snap_seq, snap = seq, payload
            elif tag in (TAG_EVENTS, TAG_ACK):
                reliable.append(dgram)
            elif tag in (TAG_CTRL, TAG_CACK):
                ctrl_dgrams.append(dgram)
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
                    self._ctrl_inbox.append(msg)
                    self._note("in", f"ctrl {msg.get('op')}")
                except ValueError:
                    pass
