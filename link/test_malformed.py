"""What the network can send that the partner's game never would: the real host, transport and
mailbox, two of them on localhost, with no games (the mailboxes are plain memory).

    python link/test_malformed.py

A HELO is taken from any address (that's how a partner is found), and on the couch so is
everything else, so none of it may stop a host's frame or fill its memory. Every packet here is
sent to a linked host, which must run its next frame; and afterwards the two still play together:
presences, events and a control message cross."""

import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from link import transport as tr  # noqa: E402
from link.host import Host  # noqa: E402
from link.mailbox import (COOP_MAGIC, IN_RING, LINK_VERSION, OUT_RING, PARTNER_PRIMS, RING_SIZE, SELF,  # noqa: E402
                          SNAP_IN_SEQ, SNAP_MAX, Mailbox, Presence)

MAILBOX = 0x80200000


class Memory:
    """A game's 8 MB of RAM with only a mailbox in it, as an adapter (link/adapter.py)."""

    def __init__(self):
        self.ram = bytearray(0x800000)
        self.write_bytes(MAILBOX, struct.pack("<II", COOP_MAGIC, LINK_VERSION))

    def read_bytes(self, address, size):
        a = address & 0x7FFFFF
        return bytes(self.ram[a:a + size])

    def write_bytes(self, address, data):
        a = address & 0x7FFFFF
        assert a + len(data) <= len(self.ram), "a write past the end of RAM"
        self.ram[a:a + len(data)] = data


class Player:
    def __init__(self, rank, clock):
        self.memory = Memory()
        self.mailbox = Mailbox(self.memory, MAILBOX)
        self.t = tr.UdpTransport()
        self.t.clock = clock
        self.host = Host(self.mailbox, self.t, rank=rank)


def bomb(size=64 << 20):
    """A few KB that unpack to `size` bytes."""
    return zlib.compress(bytes(size), 9)


def main():
    failures = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    now = [0.0]
    a, b = Player(0, lambda: now[0]), Player(1, lambda: now[0])
    a.t.connect(b.t.port)
    b.t.connect(a.t.port)

    def frames(n=1):
        for _ in range(n):
            now[0] += 1 / 60
            a.host.after_frame()
            b.host.after_frame()

    frames(5)
    check(a.host.partner_hello and b.host.partner_hello and not a.host.mismatch, "two hosts with no games shake hands")

    def survives(what, tag, payload):
        """b's address sends it to a (the worst case: a's partner itself); a runs on."""
        b.t._send_datagram(tag, payload)
        try:
            frames(2)
        except Exception as e:  # noqa: BLE001 - the failure this test is for
            check(False, f"{what}: the host's frame raised {e!r}")
            return False
        check(True, f"{what}: the frame runs on")
        return True

    hello = dict(b.host.hello)
    for what, payload in (
            ("a HELO that's a list", b"[]"),
            ("a HELO that's a string", b'"hello"'),
            ("a HELO that's null", b"null"),
            ("a HELO that isn't JSON", b"\xff\xfe{"),
            ("a HELO with a number for its sid", json.dumps(dict(hello, sid=5)).encode()),
            ("a HELO with a number for its seed", json.dumps(dict(hello, sid="x" * 8, mod=7)).encode()),
            ("a HELO with a list for its room", json.dumps(dict(hello, sid="y" * 8, room=[1])).encode()),
            ("a HELO with a list for its clock", json.dumps(dict(hello, clock=["a", "b", "c"])).encode())):
        before = a.host.restarts
        survives(what, tr.TAG_HELLO, payload)
        check(a.host.partner_hello.get("sid") == hello["sid"] and a.host.restarts == before and not a.host.mismatch,
              f"{what}: the partner is still the partner")

    survives("a BYE that's a list", tr.TAG_BYE, b"[1]")
    survives("an empty presence", tr.TAG_PRESENCE, b"")
    survives("a presence cut short", tr.TAG_PRESENCE, bytes(20))
    survives("an empty ACK", tr.TAG_ACK, b"")
    survives("an empty EVTS", tr.TAG_EVENTS, b"")
    survives("an EVTS cut short", tr.TAG_EVENTS, b"\x01\x00")
    survives("an empty CTRL and CACK", tr.TAG_CTRL, b"")
    survives("an empty CACK", tr.TAG_CACK, b"\x01")
    survives("a snapshot chunk cut short", tr.TAG_SNPC, b"\x01\x02\x03")
    survives("sprites, hits and primitives that aren't", tr.TAG_SPRT, b"\x01" * 7)
    survives("hits cut short", tr.TAG_HITS, b"\x01" * 5)
    survives("primitives that aren't zlib's", tr.TAG_PRIM, b"not zlib")
    survives("an unknown tag", b"WHAT", bytes(40))

    # Bytes that unpack to far more than they are: never unpacked past what the game can hold
    survives("primitives that unpack to 64 MB", tr.TAG_PRIM, bomb()[:1100])
    big = bomb()
    chunks = [big[i:i + tr.MAX_SNAP_CHUNK] for i in range(0, len(big), tr.MAX_SNAP_CHUNK)]
    seq_before = struct.unpack("<I", a.memory.read_bytes(MAILBOX + SNAP_IN_SEQ, 4))[0]
    for i, c in enumerate(chunks):
        b.t._send_datagram(tr.TAG_SNPC, tr._SNPC_HDR.pack(0x7000, 0, i, len(chunks)) + c)
    survives("a snapshot that unpacks to 64 MB", tr.TAG_SNPC, b"")
    check(a.t.snap_undecodable >= 1 and struct.unpack("<I", a.memory.read_bytes(MAILBOX + SNAP_IN_SEQ, 4))[0] == seq_before,
          "a snapshot that unpacks to 64 MB: counted as undecodable, never given to the game")
    check(tr.inflate(big, tr.MAX_CTRL_RAW) is None and tr.inflate(zlib.compress(b"abc"), 3) == b"abc"
          and tr.inflate(zlib.compress(b"abcd"), 3) is None and tr.inflate(zlib.compress(b"abc")[:-2], 3) is None,
          "inflate: over the limit or cut short is None, at the limit is the bytes")

    # Events and control chunks numbered far ahead: not kept (they'd be kept for ever)
    survives("events numbered a billion ahead", tr.TAG_EVENTS, struct.pack("<I", 1 << 30) + bytes(8 * 100))
    survives("a control chunk numbered a billion ahead", tr.TAG_CTRL, tr._CTRL_HDR.pack(1 << 30, 1, 0, 4) + b"abcd")
    check(not a.host.events.early and not a.host.ctrl.early, "numbered far ahead: nothing is kept waiting for the gap")

    # Control messages that aren't what the host expects (they arrive whole and in order: from b's host)
    for what, msg in (("a list", [1, 2]), ("a weapon with no data", {"op": "weapon", "hand": "x"}),
                      ("a familiar that isn't base64", {"op": "familiar", "data": "!!"}),
                      ("a familiar that unpacks to 64 MB", {"op": "familiar", "data": __import__("base64").b64encode(big).decode()}),
                      ("a status of the wrong size", {"op": "status", "data": "AAAA"})):
        b.host.ctrl.send(json.dumps(msg).encode())
        try:
            frames(3)
            check(True, f"a control message that's {what}: the frame runs on")
        except Exception as e:  # noqa: BLE001
            check(False, f"a control message that's {what}: the host's frame raised {e!r}")

    # The mailbox itself: sizes and counts it hands the game are never more than was written
    a.mailbox.put_snapshot(bytes(SNAP_MAX + 500))
    check(struct.unpack("<II", a.memory.read_bytes(MAILBOX + SNAP_IN_SEQ, 8))[1] == SNAP_MAX,
          "a snapshot bigger than the mailbox holds: cut, and the size given is what was written")
    a.mailbox.write_partner_prims(bytes(0x30 * 200))
    check(struct.unpack("<I", a.memory.read_bytes(MAILBOX + PARTNER_PRIMS, 4))[0] == 32, "200 primitives: 32 are written")
    a.memory.write_bytes(MAILBOX + OUT_RING, struct.pack("<II", 0x80000000, 5))  # a ring that makes no sense
    check(len(a.mailbox.take_events()) == RING_SIZE, "an out ring with its head far past its tail: one ring's worth is read")
    a.memory.write_bytes(MAILBOX + OUT_RING, struct.pack("<II", 0, 0))
    frames(30)  # (those 256 empty events reach b)

    # And after all that, the two still play together
    me = Presence(flags=1, stage=0x41, x=123, y=45)
    a.memory.write_bytes(MAILBOX + SELF, me.pack())
    head = struct.unpack("<I", a.memory.read_bytes(MAILBOX + OUT_RING, 4))[0]
    a.memory.write_bytes(MAILBOX + OUT_RING + 8 + (head % RING_SIZE) * 8, struct.pack("<BxHI", 5, 0, 777))
    a.memory.write_bytes(MAILBOX + OUT_RING, struct.pack("<I", head + 1))
    a.host.send_control({"op": "ping", "n": 1})
    in_before = struct.unpack("<I", b.memory.read_bytes(MAILBOX + IN_RING, 4))[0]
    frames(30)
    got = b.mailbox.partner_presence()
    check((got.stage, got.x, got.y) == (0x41, 123, 45), f"afterwards: a's presence reaches b's game ({got.stage:#x}, {got.x}, {got.y})")
    in_head = struct.unpack("<I", b.memory.read_bytes(MAILBOX + IN_RING, 4))[0]
    last = b.memory.read_bytes(MAILBOX + IN_RING + 8 + ((in_head - 1) % RING_SIZE) * 8, 8)
    check(in_head == in_before + 1 and struct.unpack("<BxHI", last) == (5, 0, 777), "afterwards: a's event reaches b's game, once")
    check({"op": "ping", "n": 1} in b.host.take_control(), "afterwards: a's control message reaches b's host")

    a.t.close()
    b.t.close()
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
