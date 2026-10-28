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

from link.connect import GAME_PORT, TIMEOUT_S, Connector  # noqa: E402
from link.host import Host  # noqa: E402
from link.natsim import CONE, KINDS, PORT_RESTRICTED, RESTRICTED, SYMMETRIC, DeadRelay, Internet, MemoryRelay, StunServer  # noqa: E402
from link.relay import Relay  # noqa: E402
from link.transport import TAG_PRESENCE, UdpTransport  # noqa: E402


class NoGame:
    """A mailbox for a game that hasn't booted: the host only does its handshake."""

    def ready(self):
        return False


class Player:
    def __init__(self, net, router, room, role, relay, stuns, clock, link=None, app="0.9.0", port=0, relays=(),
                 portmap=False):
        self.sock = net.socket(router)
        self.t = UdpTransport(port=port, sock=self.sock, bind_host="0.0.0.0")
        self.t.clock = clock
        self.host = Host(NoGame(), self.t, rank=0 if role == "host" else 1)
        if link is not None:
            self.host.hello["link"] = link
        self.host.start_connect(room, role, relay=relay, stun_servers=stuns, resolve=False,
                                lan_ip=self.sock.addr[0], app=app, relays=list(relays),
                                portmap=self._portmap(router) if portmap else (lambda port: None))
        if app is None:  # a launcher from before 0.9.0: its candidates carry no version
            self.host.connector.version = {}

    def _portmap(self, router):
        """A router that answers UPnP / NAT-PMP: it forwards the game's port (link/portmap.py)."""
        def mapped(port):
            router.forward(port, self.sock.addr)
            router.out[self.sock.addr] = port
            return (router.ip, port)
        return mapped

    def tick(self):
        self.host.handshake_tick()


class SeeingRelay(Relay):
    """The relay of link/relay.py, keeping what passed through it (to check it can't read it)."""

    def handle(self, data, addr):
        self.seen = getattr(self, "seen", []) + [data]
        super().handle(data, addr)


def session(a_kind, b_kind, same_house=False, forward=None, room_b="BAT-7K2Q", seconds=35, b_version=None,
            relay=None, port=0, with_relay=False, portmap=""):
    net = Internet()
    stuns = [StunServer(net, 3478), StunServer(net, 19302)]
    relays, rel = (), None
    if with_relay:  # an open relay on the internet (anyone's: link/relay.py)
        sock = net.socket(None)
        sock.bind(("0.0.0.0", 3479))
        rel = SeeingRelay(sock, clock=lambda: clock_t[0])
        relays = [sock.addr]
    relay = relay or MemoryRelay()
    clock_t = [0.0]
    clock = lambda: clock_t[0]
    ra = net.router(a_kind)
    rb = ra if same_house else net.router(b_kind)
    a = Player(net, ra, "BAT-7K2Q", "host", relay, [s.addr for s in stuns], clock, port=port, relays=relays,
               portmap="a" in portmap)
    b = Player(net, rb, room_b, "join", relay, [s.addr for s in stuns], clock, port=port, relays=relays,
               portmap="b" in portmap, **(b_version or {}))
    a.relay_server = rel
    if forward == "a":  # the host's router forwards the game's port to it
        ra.forward(a.t.port, a.sock.addr)
        ra.out[a.sock.addr] = a.t.port
    for _ in range(int(seconds * 60)):
        clock_t[0] += 1 / 60
        a.tick()
        b.tick()
        for s in stuns:
            s.tick()
        if rel:
            rel.poll()
        if a.host.connector.state == b.host.connector.state == "connected" or {
                a.host.connector.state, b.host.connector.state} <= {"connected", "failed"}:
            break
    return a, b


def exchanged(a, b):
    """After connecting, presences flow both ways (from the confirmed addresses only)."""
    for p, q in ((a, b), (b, a)):
        p.t.send(TAG_PRESENCE, bytes(0x2C))
        if getattr(a, "relay_server", None):  # through the relay: its turn to forward
            a.relay_server.poll()
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

    # M14: with an open relay, the pairings hole punching can't do connect too, through it; the relay
    # carries only sealed packets (it can't read a presence or a HELO)
    for ka, kb in itertools.product(KINDS, KINDS):
        if expect_connects(ka, kb):
            continue
        a, b = session(ka, kb, with_relay=True, seconds=20)
        sa, sb = a.host.connector.status(), b.host.connector.status()
        flow = sa["state"] == sb["state"] == "connected" and exchanged(a, b)
        a.tick(); b.tick()
        rel = a.relay_server
        plain = any(tag in d for d in getattr(rel, "seen", []) for tag in (b"PRES", b"HELO", b"BAT-7K2Q"))
        check(flow and sa["via"] and rel.forwarded > 0 and not plain,
              f"{ka} host + {kb} joiner, with a relay: connected through it, sealed ({sa['state']}/{sb['state']}, via {sa['via']}, plaintext seen: {plain})")
    # M14 step 3: a symmetric router that answers UPnP / NAT-PMP opens the game's port: direct
    for ka, kb, who in ((SYMMETRIC, PORT_RESTRICTED, "a"), (PORT_RESTRICTED, SYMMETRIC, "b"), (SYMMETRIC, SYMMETRIC, "a")):
        a, b = session(ka, kb, portmap=who, seconds=20)
        sa = a.host.connector.status()
        check(sa["state"] == b.host.connector.state == "connected" and sa["via"] is None and exchanged(a, b),
              f"{ka} host + {kb} joiner, the {'host' if who == 'a' else 'joiner'}'s router opens the port: connected directly")
    a, b = session(CONE, PORT_RESTRICTED, with_relay=True, seconds=20)
    check(a.host.connector.state == "connected" and a.host.connector.via is None,
          "with a relay, a pair that can punch still connects directly")

    a, b = session(PORT_RESTRICTED, PORT_RESTRICTED, same_house=True)
    lan = b.t.peer and b.t.peer[0].startswith("192.168.")
    check(a.host.connector.state == b.host.connector.state == "connected" and lan,
          f"same house: connected over the LAN (joiner's peer {b.t.peer})")

    # Same house, and the relay can't be reached (Tucker's Thor, 2026-10-23: no CA certificates):
    # the LAN broadcast to the usual port finds the partner anyway
    a, b = session(PORT_RESTRICTED, PORT_RESTRICTED, same_house=True, relay=DeadRelay(), port=GAME_PORT, seconds=5)
    check(a.host.connector.state == b.host.connector.state == "connected" and b.t.peer and b.t.peer[0].startswith("192.168."),
          f"same house, no relay: connected by the LAN broadcast within 5 s (joiner's peer {b.t.peer})")
    a, b = session(PORT_RESTRICTED, PORT_RESTRICTED, same_house=True, room_b="FOG-2222", port=GAME_PORT, seconds=5)
    check(a.t.peer is None and b.t.peer is None, "same house: another room's LAN broadcast is never accepted")

    # Apart, and the relay can't be reached: the lobby says so at once; the failure names it
    a, b = session(CONE, CONE, relay=DeadRelay(), seconds=3)
    st = a.host.connector.status()
    check(st["state"] == "waiting" and st["relay_error"], f"no relay: the lobby is told within 3 s ({st['relay_error']!r})")
    a.host.connector.timeout = 0
    a.tick()
    check("room-code server" in (a.host.connector.reason or ""), f"no relay: the failure says why ({a.host.connector.reason!r:.60})")

    # The usual port taken (two games on one PC): the next one
    s1 = UdpTransport(port=(0,), bind_host="127.0.0.1")
    s2 = UdpTransport(port=(s1.port, 0), bind_host="127.0.0.1")
    check(s2.port not in (0, s1.port), f"the usual port taken: another one ({s1.port} -> {s2.port})")
    s1.close(); s2.close()

    a, b = session(SYMMETRIC, PORT_RESTRICTED, forward="a")
    check(a.host.connector.state == b.host.connector.state == "connected",
          "symmetric host with a forwarded port + port-restricted joiner: connected")

    # A stranger (another room code) who learns our candidates and punches anyway.
    a, b = session(CONE, CONE, room_b="FOG-2222", seconds=5)
    check(a.t.peer is None and b.t.peer is None and a.host.connector.state != "connected",
          "a player with another room code is never accepted")

    # A game with no room code (joined by ip:port) answers our LAN broadcast: only a host takes it
    # (its partner typed our ip:port); a joiner with a room code never does (D100).
    net, clock = Internet(), (lambda: 0.0)
    for role, want in (("host", True), ("join", False)):
        p = Player(net, net.router(CONE), "BAT-7K2Q", role, MemoryRelay(), [], clock)
        p.host._check_hello(b'{"link": %d, "sid": "0badf00d"}' % p.host.hello["link"], ("10.0.0.9", GAME_PORT))
        check(bool(p.host.partner_hello) == want,
              f"a roomless HELO: the {role} {'takes it (ip:port)' if want else 'ignores it'}")

    # Different versions (Tucker's Thor on 0.9.0-dev, his PC still on 0.7.1): told at once, by name.
    for what, ver in (("a newer joiner", {"link": 99, "app": "1.0.0"}), ("a joiner from before 0.9.0", {"link": 8, "app": None})):
        a, b = session(CONE, CONE, b_version=ver, seconds=10)
        sa, sb = a.host.connector.status(), b.host.connector.status()
        old = ver["app"] is None  # an old joiner can't tell: only our side must
        check(sa["state"] == "failed" and (old or sb["state"] == "failed") and "same version" in sa["reason"] and (ver["app"] or "older") in sa["reason"],
              f"{what}: {'the host is' if old else 'both are'} told within 10 s ({sa['reason']!r:.70})")

    # Leaving (playtest 2026-10-25: closing the PC app left the Thor saying nothing): the partner
    # is told at once, and it's forgotten when the partner comes back (a new host, a new sid).
    a, b = session(CONE, CONE, seconds=10)
    b.host.goodbye()
    for _ in range(5):
        a.tick()
    check(a.host.status()["partner_left"], "a partner who closes the app: told at once (BYE)")
    b.host.hello["sid"] = "0newb0b0"  # its app started again
    for _ in range(120):
        a.tick()
        b.tick()
    check(not a.host.status()["partner_left"], "the partner comes back: no longer 'left'")
    a.host._check_bye(b'{"sid": "someone"}')
    check(not a.host.partner_left, "a BYE from anyone else is ignored")

    sym = Connector.__init__  # noqa: F841 - (the connector module imports cleanly)
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
