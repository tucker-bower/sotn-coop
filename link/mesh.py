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


def slot(me, other):
    """The partner slot (CoopLink partner 0, more[0], more[1]) game `me` keeps player `other` in."""
    return other if other < me else other - 1


def pair_code(code, a, b):
    """The room code a guest pair finds each other with: its own relay topic and token."""
    return f"{code}:{min(a, b)}-{max(a, b)}"


class Room:
    """3+ players online (M17, D211): this game's side of a room, and a Host per partner.

    Player 0 made the code and seats whoever joins it, one at a time: its HELO to each tells them
    their number ("seat") and who's in ("players"). Each guest pair then finds each other on a
    code of its own (pair_code), the lower number as "host"; a pair still apart after
    pair_timeout seconds goes through player 0 instead (Mesh.relay).

    new_transport(): a fresh UdpTransport (online: on any free port, the router's kind of socket).
    connect_kw: Host.start_connect's other arguments (relay, stun_servers, ...)."""

    def __init__(self, mailbox, code, hosting, new_transport, max_players=4, pair_timeout=30.0, make_host=None,
                 **connect_kw):
        """make_host(view, transport, rank): a Host set up as the app's (its castle, rules, character);
        a plain one by default."""
        from .host import Host
        from .mailbox import Partners
        self._Host = make_host or Host
        self.code, self.new_transport, self.connect_kw = code, new_transport, connect_kw
        self.max_players, self.pair_timeout = max_players, pair_timeout
        self.partners = Partners(mailbox)
        self.me = 0 if hosting else None
        self.mesh = Mesh(self.me if hosting else 1)
        self.hosts = {}  # player number -> Host
        self.players = [0]
        self._pending = None  # player 0: the Host waiting for the next joiner
        self._first = None    # a guest: its Host to player 0, before its seat is known
        self._started = {}    # a guest: player -> when its pair began finding each other
        self._seated = set()  # player 0: the seated joiners' relay ids (the next seat skips them)
        self._full_said, self._relay = None, None  # player 0: "the room is full" on the relay (#332)
        self._seated_sids = set()  # ...and their HELO sids (the next seat refuses them)
        if hosting:
            self._open_seat()
        else:
            self._first = self._host(0, 0, rank=1)
            self._first.start_connect(code, "join", **dict(connect_kw))

    def _host(self, who, k, transport=None, rank=None):
        t = transport or self.new_transport()
        if transport is None:
            self.mesh.add(who, t)
        return self._Host(self.partners.view(k), t, rank=self.me if rank is None else rank)

    def _say_full(self):
        """#332: every seat taken (the castle's Max players, D221): say so on the room's relay topic
        now and then, so a joiner with the code hears "The room is full" rather than waiting. A seat
        that opens again posts a host message, newer, which the joiner takes instead."""
        from .connect import REPUBLISH_S, default_relay, room_token, room_topic
        clock = next(iter(self.hosts.values())).transport.clock
        now = clock()
        if self._full_said is not None and now - self._full_said < REPUBLISH_S:
            return
        self._full_said = now
        if self._relay is None:
            self._relay = self.connect_kw.get("relay") or default_relay()
        self._relay.publish(room_topic(self.code), {"role": "full", "token": room_token(self.code), "nonce": now,
                                                    "players": len(self.players), "max": self.max_players,
                                                    "seated": sorted(i for i in self._seated if i)})

    def _open_seat(self):
        seat = len(self.players)
        if seat >= self.max_players:
            self._pending = None
            return
        self._pending = self._host(seat, slot(0, seat))
        self._pending.refuse_sids = self._seated_sids
        self._pending.start_connect(self.code, "host", exclude=self._seated, **dict(self.connect_kw))

    def _tell_roster(self):
        for n, host in self.hosts.items():
            host.hello.update(seat=n, players=list(self.players))

    def tick(self, game_running=False):
        """Once a frame: every link's handshake, or its whole frame once the game runs."""
        for host in self.all_hosts():
            if game_running:
                host.after_frame()
            else:
                host.handshake_tick()
        if self.me == 0:
            p = self._pending
            if p is not None and p.connector and p.connector.state == "connected":
                seat = len(self.players)
                # the joiner's relay id: from its relay message, or its HELO (it may connect first
                # another way, on a LAN, and the room's "full" must still name it: ui_online)
                self._seated.add(p.connector.their_id or (p.partner_hello or {}).get("rid"))
                self._seated_sids.add(p.partner_hello.get("sid"))
                p.only_sid = p.partner_hello.get("sid")
                self.hosts[seat] = p
                self.players.append(seat)
                self._tell_roster()
                self._open_seat()
            elif p is not None and p.connector and p.connector.state == "failed":
                self.mesh.links.pop(len(self.players), None)
                self._open_seat()  # that joiner couldn't reach us: wait for the next
            elif p is None and self.hosts:
                self._say_full()
            return
        first = self._first
        if self.me is None and first.partner_hello and isinstance(first.partner_hello.get("seat"), int):
            self.me = self.mesh.me = first.partner_hello["seat"]
            first.rank = self.me
            first.only_sid = first.partner_hello.get("sid")
            self.hosts[0] = first
            self.mesh.add(0, first.transport)
        if self.me is None:
            return
        roster = self.hosts[0].partner_hello.get("players") or []
        now = self.hosts[0].transport.clock()
        for n in roster:
            if not isinstance(n, int) or n in (0, self.me) or n in self.hosts or not 0 < n < self.max_players:
                continue
            h = self._host(n, slot(self.me, n))
            h.start_connect(pair_code(self.code, self.me, n), "host" if self.me < n else "join", **dict(self.connect_kw))
            self.hosts[n] = h
            self._started[n] = now
        for n, h in list(self.hosts.items()):
            if n == 0 or n not in self._started:
                continue
            state = h.connector.state if h.connector else "connected"
            if state == "failed" or (state != "connected" and now - self._started[n] > self.pair_timeout):
                h.transport.close()
                self.hosts[n] = self._host(n, slot(self.me, n), transport=self.mesh.relay(n))
                del self._started[n]
            elif state == "connected" and h.partner_hello:
                h.only_sid = h.partner_hello.get("sid")
                del self._started[n]

    def all_hosts(self):
        out = list(self.hosts.values())
        for h in (self._pending, self._first):
            if h is not None and h not in out:
                out.append(h)
        return out

    def relayed(self):
        """The players this game reaches only through player 0."""
        return sorted(n for n, t in self.mesh.links.items() if isinstance(t, RelayTransport))

    def status(self):
        """The room as the app's lobby shows it: this game's number, who's in, and each partner's
        link (its HELO, ping, connect state)."""
        out = {"me": self.me, "players": list(self.players) if self.me == 0 else
               list((self.hosts[0].partner_hello or {}).get("players") or []) if 0 in self.hosts else [],
               "partners": {}}
        for n, h in self.hosts.items():
            st = h.connect_status() or {}
            out["partners"][n] = {**h.status(), "state": st.get("state", "connected")}
        waiting = self._first if self.me is None else self._pending if self.me == 0 else None
        if waiting is not None:
            out["waiting"] = {**waiting.status(), **(waiting.connect_status() or {})}
        return out

    def goodbye(self):
        for h in self.all_hosts():
            h.goodbye()
