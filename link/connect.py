"""Finding the partner over the internet, from a room code (design/M7b-netcode.md).

Both players are usually behind home routers that only let a packet in through a hole their
own PC opened by sending out first, to that same address. So:
1. Candidates: each side learns its own addresses: on the LAN, and as the internet sees it
   (STUN, asked from the game's own socket, because that's the hole that matters). Asking two
   STUN servers also tells whether the router gives a different port per destination
   ("symmetric"), which hole punching can't get through.
2. Rendezvous: both sides post their candidates to the room's relay topic (ntfy.sh: no
   account, no server of ours), and read the other side's.
3. Punching: both send HELO to every candidate of the other, ten times a second. The first
   HELO that comes back with the room's token is the partner (link/host.py accepts it), and
   from then on only that address is listened to.
The relay only ever sees the room's hashed topic and the two candidate lists."""

import hashlib
import json
import re
import socket
import threading
import time
import urllib.request

from .transport import TAG_HELLO

STUN_SERVERS = (("stun.l.google.com", 19302), ("stun.cloudflare.com", 3478))
STUN_WAIT_S = 1.5
PUNCH_EVERY_S = 0.1
REPUBLISH_S = 20.0
TIMEOUT_S = 30.0


def room_topic(code):
    clean = re.sub(r"[\s\-_]", "", code.upper())
    return "sotn-coop-" + hashlib.sha256(f"sotn-coop-v2:{clean}".encode()).hexdigest()[:24]


def room_token(code):
    """Sent in HELO: proves a packet comes from someone who knows the room code."""
    clean = re.sub(r"[\s\-_]", "", code.upper())
    return hashlib.sha256(f"sotn-coop-token:{clean}".encode()).hexdigest()[:16]


class NtfyRelay:
    """The rendezvous relay: ntfy.sh topics, public and account-free. Publishing and reading
    happen on background threads; poll() returns what has come in so far."""

    URL = "https://ntfy.sh"

    def __init__(self):
        self._msgs = {}
        self._subs = set()
        self._lock = threading.Lock()

    def publish(self, topic, msg):
        def post():
            try:
                req = urllib.request.Request(f"{self.URL}/{topic}", data=json.dumps(msg).encode(), method="POST")
                urllib.request.urlopen(req, timeout=5).read()
            except Exception:  # noqa: BLE001 - offline or blocked: the connector times out with a reason
                pass
        threading.Thread(target=post, daemon=True).start()

    def poll(self, topic):
        if topic not in self._subs:
            self._subs.add(topic)
            self._msgs[topic] = []
            threading.Thread(target=self._stream, args=(topic,), daemon=True).start()
        with self._lock:
            return list(self._msgs[topic])

    def _stream(self, topic):
        """One long-lived streaming request (one, not one a second: ntfy.sh limits requests)."""
        since = "10m"
        while True:
            try:
                with urllib.request.urlopen(f"{self.URL}/{topic}/json?since={since}", timeout=60) as resp:
                    for line in resp:
                        outer = json.loads(line)
                        if outer.get("event") == "message":
                            since = outer.get("id", since)
                            try:
                                msg = json.loads(outer.get("message", ""))
                            except ValueError:
                                continue
                            with self._lock:
                                self._msgs[topic].append(msg)
            except Exception:  # noqa: BLE001 - dropped or timed out: reconnect
                time.sleep(2)


class FileRelay:
    """The relay as a folder of topic files: for tests and for two games on one PC."""

    def __init__(self, folder):
        self.folder = str(folder)

    def _path(self, topic):
        from pathlib import Path
        p = Path(self.folder)
        p.mkdir(parents=True, exist_ok=True)
        return p / f"{topic}.jsonl"

    def publish(self, topic, msg):
        with open(self._path(topic), "a") as f:
            f.write(json.dumps(msg) + "\n")

    def poll(self, topic):
        try:
            return [json.loads(line) for line in self._path(topic).read_text().splitlines() if line]
        except (OSError, ValueError):
            return []


def default_relay():
    """ntfy.sh; or a folder, when COOP_RELAY_DIR says so (tests: two launchers on one PC)."""
    import os
    folder = os.environ.get("COOP_RELAY_DIR")
    return FileRelay(folder) if folder else NtfyRelay()


class Connector:
    """Run by the host every frame (tick) until the partner is found."""

    def __init__(self, transport, room, role, relay, hello, stun_servers=STUN_SERVERS,
                 lan_ip=None, timeout=TIMEOUT_S, resolve=True):
        """role: "host" or "join". hello: () -> the HELO payload to punch with."""
        self.t, self.room, self.role, self.relay, self.hello = transport, room, role, relay, hello
        self.topic = room_topic(room)
        self.lan_ip = lan_ip
        self.timeout = timeout
        self.state = "starting"
        self.reason = None
        self.nonce = transport.clock()  # this attempt (the newest message of each side wins)
        self.mine, self.theirs = [], []
        self.their_nat = None
        self.nat = None
        self._t0 = None
        self._stun = []
        self._stun_sent = None
        self._published = None
        self._punched = 0.0
        self._resolve = resolve
        self._servers = list(stun_servers)
        self._resolved = None
        if resolve:
            threading.Thread(target=self._resolve_servers, daemon=True).start()
        else:
            self._resolved = self._servers

    def _resolve_servers(self):
        out = []
        for host, port in self._servers:
            try:
                out.append((socket.gethostbyname(host), port))
            except OSError:
                pass
        self._resolved = out

    def status(self):
        return {"state": self.state, "reason": self.reason, "nat": self.nat, "their_nat": self.their_nat,
                "mine": self.mine, "theirs": self.theirs}

    def tick(self):
        if self.state in ("connected", "failed"):
            return self.state
        now = self.t.clock()
        if self._t0 is None:
            self._t0 = now
        if self.t.peer is not None and self.t.peer_confirmed:
            self.state = "connected"
            return self.state
        # 1. candidates
        if self._stun_sent is None and self._resolved is not None:
            for server in self._resolved:
                self.t.stun_request(server)
            self._stun_sent = now
        if self.state == "starting":
            got = self.t.stun_results
            done = self._stun_sent is not None and (len(got) >= len(self._resolved or ()) or now - self._stun_sent > STUN_WAIT_S)
            if done or now - self._t0 > STUN_WAIT_S * 2:
                public = sorted(set(got.values()))
                self.nat = "none" if not public else ("symmetric" if len({p for _, p in public}) > 1 else "cone")
                lan = (self.lan_ip or self.t.sock.getsockname()[0], self.t.port)
                self.mine = [list(lan)] + [list(p) for p in public if p != lan]
                self.state = "waiting"
        # 2. rendezvous
        if self.state in ("waiting", "punching"):
            if self._published is None or now - self._published > REPUBLISH_S:
                self.relay.publish(self.topic, {"role": self.role, "nonce": self.nonce, "cands": self.mine,
                                                "nat": self.nat, "token": room_token(self.room)})
                self._published = now
            other = "join" if self.role == "host" else "host"
            msgs = [m for m in self.relay.poll(self.topic)
                    if m.get("role") == other and m.get("token") == room_token(self.room)]
            if msgs:
                newest = max(msgs, key=lambda m: m.get("nonce", 0))
                cands = [tuple(c) for c in newest.get("cands", []) if len(c) == 2]
                if cands != self.theirs:
                    self.theirs, self.their_nat = cands, newest.get("nat")
                self.state = "punching"
        # 3. punching
        if self.state == "punching" and now - self._punched >= PUNCH_EVERY_S:
            self._punched = now
            for c in self.theirs:
                self.t.probe(c, TAG_HELLO, self.hello())
        if now - self._t0 > self.timeout:
            self.state = "failed"
            self.reason = self._why()
        return self.state

    def _why(self):
        if not self.theirs:
            return ("Your partner's game never showed up for this room code. Check the code, and that "
                    "both of you are online.")
        if "symmetric" in (self.nat, self.their_nat):
            who = "Your" if self.nat == "symmetric" else "Your partner's"
            return (f"{who} internet connection gives every connection a different port (a phone "
                    "hotspot or some ISPs do this), so the two games can't reach each other directly. "
                    "Try another network, or forward a UDP port on the router (Help ▸ Online troubleshooting).")
        return ("Both games found each other but no packets got through: a firewall may be blocking "
                "the game. Allow SOTN Co-op through Windows Firewall when asked, and try again.")
