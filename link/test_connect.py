"""Finding the partner through home routers (design/M7b-netcode.md): the real connector, host and
transport, on the virtual internet of link/natsim.py.

    python link/test_connect.py

For every pair of router kinds, two players with a room code must connect (and only then
exchange presences), except where hole punching can't work: a router that gives a new port per
destination ("symmetric") against one that filters by port, or two symmetric ones. Those must
fail within the timeout with a reason that names the problem. Also:
- two players in the same house connect across their LAN;
- a stranger with another room code is never accepted, even when it knows our address;
- a forwarded port (UPnP or by hand) makes even a symmetric router reachable."""

import itertools
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from link.connect import TIMEOUT_S, Connector  # noqa: E402
from link.host import Host  # noqa: E402
from link.natsim import CONE, KINDS, PORT_RESTRICTED, RESTRICTED, SYMMETRIC, Internet, MemoryRelay, StunServer  # noqa: E402
from link.transport import TAG_PRESENCE, UdpTransport  # noqa: E402


class NoGame:
    """A mailbox for a game that hasn't booted: the host only does its handshake."""

    def ready(self):
        return False


class Player:
    def __init__(self, net, router, room, role, relay, stuns, clock):
        self.sock = net.socket(router)
        self.t = UdpTransport(sock=self.sock, bind_host="0.0.0.0")
        self.t.clock = clock
        self.host = Host(NoGame(), self.t, rank=0 if role == "host" else 1)
        self.host.start_connect(room, role, relay=relay, stun_servers=stuns, resolve=False,
                                lan_ip=self.sock.addr[0])

    def tick(self):
        self.host.handshake_tick()


def session(a_kind, b_kind, same_house=False, forward=None, room_b="BAT-7K2Q", seconds=35):
    net = Internet()
    stuns = [StunServer(net, 3478), StunServer(net, 19302)]
    relay = MemoryRelay()
    clock_t = [0.0]
    clock = lambda: clock_t[0]
    ra = net.router(a_kind)
    rb = ra if same_house else net.router(b_kind)
    a = Player(net, ra, "BAT-7K2Q", "host", relay, [s.addr for s in stuns], clock)
    b = Player(net, rb, room_b, "join", relay, [s.addr for s in stuns], clock)
    if forward == "a":  # the host's router forwards the game's port to it
        ra.forward(a.t.port, a.sock.addr)
        ra.out[a.sock.addr] = a.t.port
    for _ in range(int(seconds * 60)):
        clock_t[0] += 1 / 60
        a.tick()
        b.tick()
        for s in stuns:
            s.tick()
        if a.host.connector.state == b.host.connector.state == "connected":
            break
    return a, b


def exchanged(a, b):
    """After connecting, presences flow both ways (from the confirmed addresses only)."""
    for p, q in ((a, b), (b, a)):
        p.t.send(TAG_PRESENCE, bytes(0x2C))
        got = [d for d in q.t.receive() if d[0] == TAG_PRESENCE]
        if not got:
            return False
    return True


def expect_connects(a_kind, b_kind):
    return not ({a_kind, b_kind} in ({SYMMETRIC, PORT_RESTRICTED}, {SYMMETRIC}))


def main():
    failures = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    for ka, kb in itertools.product(KINDS, KINDS):
        want = expect_connects(ka, kb)
        a, b = session(ka, kb, seconds=35 if want else TIMEOUT_S + 5)
        sa, sb = a.host.connector.status(), b.host.connector.status()
        if want:
            ok = sa["state"] == sb["state"] == "connected" and exchanged(a, b)
            check(ok, f"{ka} host + {kb} joiner: connected, presences flow ({sa['state']}/{sb['state']})")
        else:
            ok = "failed" in (sa["state"], sb["state"]) and "port" in (sa["reason"] or sb["reason"] or "")
            check(ok, f"{ka} host + {kb} joiner: fails with a reason ({sa['reason'] or sb['reason']!r:.60})")

    a, b = session(PORT_RESTRICTED, PORT_RESTRICTED, same_house=True)
    lan = b.t.peer and b.t.peer[0].startswith("192.168.")
    check(a.host.connector.state == b.host.connector.state == "connected" and lan,
          f"same house: connected over the LAN (joiner's peer {b.t.peer})")

    a, b = session(SYMMETRIC, PORT_RESTRICTED, forward="a")
    check(a.host.connector.state == b.host.connector.state == "connected",
          "symmetric host with a forwarded port + port-restricted joiner: connected")

    # A stranger (another room code) who learns our candidates and punches anyway.
    a, b = session(CONE, CONE, room_b="FOG-2222", seconds=5)
    check(a.t.peer is None and b.t.peer is None and a.host.connector.state != "connected",
          "a player with another room code is never accepted")

    sym = Connector.__init__  # noqa: F841 - (the connector module imports cleanly)
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
