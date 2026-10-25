"""A virtual internet with home routers, for testing how two players find each other.

Real players sit behind NAT routers, which decide what gets in. This models the kinds that
matter (RFC 4787), with virtual sockets the transport can use in place of real ones:
- mapping: endpoint-independent (one public port per socket, "cone"), or endpoint-dependent
  (a new public port per destination: "symmetric", common in phone networks and CGNAT);
- filtering: open ("full cone"), by address ("restricted"), or by address and port
  ("port restricted", the most common home router).
A router lets a packet in only through a mapping its own socket made, and only from where the
filtering allows: so both sides must send first (hole punching).

Also: public STUN servers that answer the way real ones do, and an in-memory relay standing in
for ntfy.sh. Delivery is instant: link/netsim.py models delay; this models reachability."""

import collections
import itertools
import socket
import struct

from .rendezvous import MAGIC_COOKIE

CONE, RESTRICTED, PORT_RESTRICTED, SYMMETRIC = "full cone", "restricted", "port restricted", "symmetric"
KINDS = (CONE, RESTRICTED, PORT_RESTRICTED, SYMMETRIC)


class Internet:
    def __init__(self):
        self.sockets = {}   # (ip, port) -> VirtualSocket
        self.routers = {}   # public ip -> Router
        self._ips = itertools.count(1)

    def public_ip(self):
        return f"203.0.113.{next(self._ips)}"

    def router(self, kind=PORT_RESTRICTED):
        r = Router(self, self.public_ip(), kind)
        self.routers[r.ip] = r
        return r

    def socket(self, router=None):
        """A UDP socket on a PC behind `router` (None: on the public internet)."""
        return VirtualSocket(self, router)

    def deliver(self, src, dst, data):
        """src, dst: public addresses. Into a router, or straight to a public socket."""
        r = self.routers.get(dst[0])
        if r:
            r.inbound(src, dst, data)
        elif dst in self.sockets and self.sockets[dst].router is None:  # private ones aren't reachable
            self.sockets[dst].queue.append((data, src))


class Router:
    def __init__(self, net, ip, kind):
        self.net, self.ip, self.kind = net, ip, kind
        self.lan = f"192.168.{len(net.routers) + 1}"
        self._hosts = itertools.count(2)
        self._ports = itertools.count(40000)
        self.out = {}        # mapping key -> public port
        self.back = {}       # public port -> (private address, destination or None)
        self.sent_to = collections.defaultdict(set)  # public port -> {(ip, port) sent to}
        self.forwards = {}   # public port -> private address (UPnP / port forwarding)
        self.dropped = 0

    def private_ip(self):
        return f"{self.lan}.{next(self._hosts)}"

    def outbound(self, src, dst, data):
        if dst[0] in ("255.255.255.255", self.lan + ".255"):  # a LAN broadcast: every PC in the house
            for addr, sock in list(self.net.sockets.items()):
                if sock.router is self and addr[1] == dst[1] and addr != src:
                    sock.queue.append((data, src))
            return
        if dst[0].startswith(self.lan + "."):  # same house: straight across the LAN
            if dst in self.net.sockets:
                self.net.sockets[dst].queue.append((data, src))
            return
        key = (src, dst) if self.kind == SYMMETRIC else src
        port = self.out.get(key)
        if port is None:
            port = next(self._ports)
            self.out[key] = port
            self.back[port] = (src, dst if self.kind == SYMMETRIC else None)
        for p, private in self.forwards.items():
            if private == src:
                port = p  # a forwarded port keeps its number on the way out (UPnP)
        self.sent_to[port].add(dst)
        self.net.deliver((self.ip, port), dst, data)

    def inbound(self, src, dst, data):
        port = dst[1]
        if port in self.forwards:
            target = self.forwards[port]
        elif port in self.back:
            target, only = self.back[port]
            seen = self.sent_to[port]
            ok = {CONE: True,
                  RESTRICTED: any(ip == src[0] for ip, _ in seen),
                  PORT_RESTRICTED: src in seen,
                  SYMMETRIC: src == only}[self.kind]
            if not ok:
                self.dropped += 1
                return
        else:
            self.dropped += 1
            return
        if target in self.net.sockets:
            self.net.sockets[target].queue.append((data, src))

    def forward(self, public_port, private):
        self.forwards[public_port] = private


class VirtualSocket:
    """Enough of a UDP socket for UdpTransport."""

    def __init__(self, net, router=None):
        self.net, self.router = net, router
        self.ip = router.private_ip() if router else net.public_ip()
        self.addr = None
        self.queue = collections.deque()

    def bind(self, addr):
        port = addr[1] or 50000 + len(self.net.sockets)
        self.addr = (self.ip, port)
        self.net.sockets[self.addr] = self

    def getsockname(self):
        return self.addr

    def setblocking(self, flag):
        pass

    def setsockopt(self, *a):
        pass

    def sendto(self, data, dst):
        if self.router:
            self.router.outbound(self.addr, (dst[0], int(dst[1])), data)
        else:
            self.net.deliver(self.addr, (dst[0], int(dst[1])), data)

    def recvfrom(self, n):
        if not self.queue:
            raise BlockingIOError
        return self.queue.popleft()

    def close(self):
        self.net.sockets.pop(self.addr, None)


class StunServer:
    """Answers RFC 5389 binding requests with the address it saw (XOR-MAPPED-ADDRESS)."""

    def __init__(self, net, port=3478):
        self.sock = VirtualSocket(net)
        self.sock.bind(("0.0.0.0", port))
        self.addr = self.sock.addr

    def tick(self):
        while self.sock.queue:
            data, src = self.sock.queue.popleft()
            if len(data) < 20:
                continue
            msg_type, _, cookie, tx = struct.unpack_from(">HHI12s", data)
            if msg_type != 0x0001 or cookie != MAGIC_COOKIE:
                continue
            ip = struct.unpack(">I", socket.inet_aton(src[0]))[0] ^ MAGIC_COOKIE
            attr = struct.pack(">HHBBHI", 0x0020, 8, 0, 1, src[1] ^ (MAGIC_COOKIE >> 16), ip)
            self.sock.sendto(struct.pack(">HHI12s", 0x0101, len(attr), MAGIC_COOKIE, tx) + attr, src)


class DeadRelay:
    """A relay that can't be reached (Android without CA certificates, ntfy.sh down or blocked)."""

    error = post_error = "URLError(no route)"

    def publish(self, topic, msg):
        pass

    def poll(self, topic):
        return []


class MemoryRelay:
    """The rendezvous relay (link/rendezvous.Relay), in memory: topics of messages."""

    def __init__(self):
        self.topics = collections.defaultdict(list)

    def publish(self, topic, msg):
        self.topics[topic].append(dict(msg))

    def poll(self, topic):
        return list(self.topics[topic])
