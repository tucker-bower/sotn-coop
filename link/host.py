"""One host per game. Call after_frame() once per emulated frame, while the emulator is paused."""

import collections
import json
import struct
import time

from .mailbox import EVENT_SIZE, LINK_VERSION, Presence
from .transport import (TAG_ACK, TAG_CACK, TAG_CTRL, TAG_EVENTS, TAG_HELLO, TAG_PRESENCE, TAG_SNAP,
                        ReliableChannel, ReliableMessages)

HELLO_EVERY = 60  # frames


class Host:
    def __init__(self, mailbox, transport, rank=0, patch_crc=None):
        """rank: 0 or 1, distinct per game; breaks shared-room authority ties (design/M4).
        patch_crc: the co-op disc's (the patch's target CRC32): partners must match."""
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
        self.hello = {"link": LINK_VERSION, "patch": patch_crc}
        self.partner_hello = None
        self.mismatch = None  # why the partner was refused, in words
        self._frames = 0

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

    def status(self):
        """Connection and handshake status for the launcher UI and tests."""
        age = None if self.transport.last_rx_time is None else round(time.monotonic() - self.transport.last_rx_time, 2)
        return {
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

    def _check_hello(self, payload):
        try:
            theirs = json.loads(payload)
        except ValueError:
            return
        self.partner_hello = theirs
        if theirs.get("link") != self.hello["link"]:
            self.mismatch = (f"Your partner's co-op version is different (link {theirs.get('link')}, "
                             f"yours {self.hello['link']}): both need the same version.")
        elif theirs.get("patch") and self.hello["patch"] and theirs["patch"] != self.hello["patch"]:
            self.mismatch = "Your partner's co-op disc is a different version: both need the same."
        else:
            self.mismatch = None

    def handshake_tick(self):
        """Exchanges HELO before emulation starts (online connection lobby)."""
        if self._frames % 15 == 0:
            self.transport.send(TAG_HELLO, json.dumps(self.hello).encode())
        self._frames += 1
        for tag, _, payload in self.transport.receive():
            if tag == TAG_HELLO:
                self._check_hello(payload)
        return self.status()

    def after_frame(self):
        if not self.mailbox.ready():  # module not loaded yet (boot), or a different module
            return
        if self._frames % HELLO_EVERY == 0:
            self.transport.send(TAG_HELLO, json.dumps(self.hello).encode())
        self._frames += 1
        if self.mismatch:  # refused: still say hello (the partner may update), relay nothing
            for tag, _, payload in self.transport.receive():
                if tag == TAG_HELLO:
                    self._check_hello(payload)
            return
        self.mailbox.set_rank(self.rank)
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
        for tag, seq, payload in self.transport.receive():
            if tag == TAG_PRESENCE and seq > self._latest_seq:  # UDP may reorder: keep the newest
                self._latest_seq, latest = seq, payload
            elif tag == TAG_SNAP and seq > self._snap_seq:
                self._snap_seq, snap = seq, payload
            elif tag in (TAG_EVENTS, TAG_ACK):
                reliable.append((tag, seq, payload))
            elif tag in (TAG_CTRL, TAG_CACK):
                ctrl_dgrams.append((tag, seq, payload))
            elif tag == TAG_HELLO:
                self._check_hello(payload)
                if self.mismatch:
                    return
        if latest is not None:
            self.mailbox.write_partner(Presence.unpack(latest))
            self.received += 1
        if snap is not None:
            self.mailbox.put_snapshot(snap)
            self._note("in", f"snapshot {self._snap_seq} ({len(snap)} bytes)")
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
