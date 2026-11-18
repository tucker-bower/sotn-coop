"""3+ players (M17, D211): a game's links to each of its partners, one transport each, and the
way round through player 0 for a pair that can't reach each other.

Player 0 made the room. A guest pair with no link of its own sends through player 0: each wraps
its datagram in TAG_FWD with the other's number, and player 0 sends it on in TAG_FWD with the
sender's. On both guests a RelayTransport stands in for the missing link, so the host above it
is the same as for a direct one."""

import collections

from .transport import TAG_FWD, UdpTransport


class _RelaySocket:
    """What a RelayTransport sends and receives through: the link to player 0."""

    def __init__(self, via, who):
        self.via, self.who = via, who
        self.inbox = collections.deque(maxlen=4096)

    def bind(self, addr):
        pass

    def setblocking(self, flag):
        pass

    def getsockname(self):
        return ("relay", self.who)

    def sendto(self, pkt, addr):
        self.via._send_datagram(TAG_FWD, bytes([self.who]) + pkt)

    def recvfrom(self, size):
        if not self.inbox:
            raise BlockingIOError
        return self.inbox.popleft(), ("relay", self.who)

    def close(self):
        pass


class RelayTransport(UdpTransport):
    """A guest's link to another guest, through player 0's transport `via`."""

    def __init__(self, via, who):
        self.relay = _RelaySocket(via, who)
        super().__init__(sock=self.relay)
        self.clock = via.clock
        self.connect(("relay", who))


class Mesh:
    """One game's transports, by the other player's number. me: this game's number (0 made the
    room). Guest pairs that can't link go through player 0 (relay())."""

    def __init__(self, me):
        self.me = me
        self.links = {}
        self.forwarded = 0  # datagrams player 0 passed between guests

    def add(self, who, transport):
        self.links[who] = transport
        transport.on_forward = lambda n, raw, src=who: self._forward(src, n, raw)
        return transport

    def relay(self, who):
        """A link to guest `who` through player 0 (both guests call it for each other)."""
        if self.me == 0 or 0 not in self.links:
            raise ValueError("only a guest linked to player 0 can go through it")
        return self.add(who, RelayTransport(self.links[0], who))

    def _forward(self, src, n, raw):
        if self.me == 0:  # from guest src, for guest n
            to = self.links.get(n)
            if to is not None and n != src:
                self.forwarded += 1
                to._send_datagram(TAG_FWD, bytes([src]) + raw)
        elif src == 0:  # player 0 passing on what guest n sent
            link = self.links.get(n)
            if isinstance(link, RelayTransport):
                link.relay.inbox.append(raw)
