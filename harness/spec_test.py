"""M6 criterion 8: a partner written from docs/link-protocol.md alone.

The test is the partner: a raw UDP socket that speaks the protocol as the document describes
it, with its own encoding (nothing from link/), against our host and a real game. If someone
writes a host from the document (Android, an emulator plugin), this is what it must do."""

import json
import socket
import struct

from scenario import scenario  # first: puts `link` on the path

from emu import Emu  # noqa: F401
from module import COOP_DISC

HEADER = struct.Struct("<4sI")
PRESENCE = 0x2C
GOLD = 0x80097964 + 0x28C  # g_Status.gold (the test reads the game; the partner doesn't)


class SpecPartner:
    """The protocol, from the document."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.peer = None
        self.seq = 0
        self.next_event = 1

    def send(self, tag, payload):
        self.seq += 1
        self.sock.sendto(HEADER.pack(tag, self.seq) + payload, self.peer)

    def receive(self):
        out = []
        while True:
            try:
                data = self.sock.recv(65536)
            except BlockingIOError:
                return out
            tag, seq = HEADER.unpack_from(data)
            out.append((tag, seq, data[HEADER.size:]))

    def presence(self, flags, stage, room, x, y):
        p = bytearray(PRESENCE)
        p[0] = flags
        struct.pack_into("<H", p, 0x04, stage)
        struct.pack_into("<hh", p, 0x08, *room)
        struct.pack_into("<hh", p, 0x0C, x, y)
        return bytes(p)

    def events(self, *events):
        """Sends events (type, a, b), numbered from 1."""
        body = b"".join(struct.pack("<BxHI", t, a, b) for t, a, b in events)
        self.send(b"EVTS", struct.pack("<I", self.next_event) + body)
        self.next_event += len(events)


@scenario("entrance", COOP_DISC)
def link_spec_conformance(run):
    """The host speaks docs/link-protocol.md: HELO, PRES, reliable EVTS/ACK both ways, and refusing
    a partner with another link version."""
    from link.adapter import HarnessAdapter
    from link.host import Host
    from link.mailbox import Mailbox
    from link.transport import UdpTransport
    from module import symbols
    e = run.emu
    mailbox = Mailbox(HarnessAdapter(e), symbols()["g_CoopLink"])
    transport = UdpTransport()
    host = Host(mailbox, transport, rank=0)
    partner = SpecPartner()
    transport.connect(partner.port)
    partner.peer = ("127.0.0.1", transport.port)
    got = {}

    def frame(n=1, partner_presence=True):
        for _ in range(n):
            if partner_presence:
                partner.send(b"PRES", partner.presence(1, 0x41, (20, 39), 90, 136))
            run.step(1)
            host.after_frame()
            for tag, _, payload in partner.receive():
                got.setdefault(tag, []).append(payload)

    frame(70)
    hello = [json.loads(p) for p in got.get(b"HELO", [])]
    run.expect(hello and hello[0]["link"] == 8, "the host says HELO with link version 8", hello=hello[:1])
    partner.send(b"HELO", json.dumps({"link": 8, "patch": None}).encode())
    pres = got.get(b"PRES", [])
    run.expect(pres and len(pres[-1]) == PRESENCE, "PRES every frame, 0x2C bytes", count=len(pres))
    me = pres[-1]
    run.expect(me[0] & 1 and struct.unpack_from("<H", me, 4)[0] == 0x41, "its presence: in play, castle entrance",
               flags=me[0], stage=hex(struct.unpack_from("<H", me, 4)[0]))
    run.expect(mailbox.partner_age() == 0 and mailbox.partner_presence().x == 90, "our PRES reached the game",
               age=mailbox.partner_age())

    gold = e.read(GOLD, "<i")
    got.clear()
    partner.events((5, 0, 123))  # GOLD +123
    frame(5)
    run.expect(e.read(GOLD, "<i") == gold + 123, "our GOLD event was applied", was=gold, now=e.read(GOLD, "<i"))
    acks = [struct.unpack_from("<I", p)[0] for p in got.get(b"ACK ", [])]
    run.expect(acks and acks[-1] == 1, "and acked (delivered = 1)", acks=acks)
    partner.events((5, 0, 123))  # the same number again would be a duplicate: this is event 2
    frame(5)
    run.expect(e.read(GOLD, "<i") == gold + 246, "event 2 applied once", now=e.read(GOLD, "<i"))

    got.clear()
    e.write(GOLD, e.read(GOLD, "<i") + 50, "<i")  # the game's own change: it sends GOLD +50
    frame(5)
    evts = got.get(b"EVTS", [])
    run.expect(evts, "the game's event came as EVTS")
    records = {}  # number -> (type, a, b): the game sends its other events too (castle flags)
    for d in evts:
        first = struct.unpack_from("<I", d)[0]
        for k in range((len(d) - 4) // 8):
            records[first + k] = struct.unpack_from("<BxHI", d, 4 + 8 * k)
    gold_events = [n for n, (t, a, b) in records.items() if t == 5 and b == 50]
    run.expect(gold_events, "GOLD +50 among them, numbered", events=sorted(records.items())[:6])
    first = max(records)
    got.clear()
    frame(40)  # no ack yet: it's resent every 15 frames
    run.expect(len(got.get(b"EVTS", [])) >= 2, "unacked events are resent", resends=len(got.get(b"EVTS", [])))
    partner.send(b"ACK ", struct.pack("<I", first))
    frame(2)
    got.clear()
    frame(40)
    run.expect(not got.get(b"EVTS"), "and not after the ack")

    partner.send(b"HELO", json.dumps({"link": 7, "patch": None}).encode())
    frame(3)
    run.expect(host.mismatch and "version" in host.mismatch, "a partner with link 7 is refused", why=host.mismatch)
    got.clear()
    frame(70)
    run.expect(not got.get(b"PRES") and got.get(b"HELO"), "then only HELO is sent (nothing relayed)",
               sent={k.decode(): len(v) for k, v in got.items()})
    partner.send(b"HELO", json.dumps({"link": 8, "patch": None}).encode())
    frame(3)
    run.expect(host.mismatch is None, "a matching HELO lifts the refusal")
    transport.close()
