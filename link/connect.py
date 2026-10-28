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
4. On the same Wi-Fi, without the relay: both also broadcast HELO to the game's usual port
   (GAME_PORT, which every game tries first), so two games in one house find each other even
   when the relay or STUN can't be reached (Tucker's Thor test, 2026-10-24).
The relay only ever sees the room's hashed topic and the two candidate lists."""

import hashlib
import json
import logging
import os
import re
import socket
import ssl
import threading
import time
import urllib.request

from .transport import TAG_HELLO

STUN_SERVERS = (("stun.l.google.com", 19302), ("stun.cloudflare.com", 3478))
STUN_WAIT_S = 1.5
PUNCH_EVERY_S = 0.1
REPUBLISH_S = 20.0
RETRY_S = 5.0   # republishing while the relay is failing (ntfy.sh allows one request per 5 s)
GAME_PORT = 47811  # the game's port when it's free (the launcher asks for it first), for the LAN broadcast
BROADCAST_EVERY_S = 0.5
log = logging.getLogger(__name__)
TIMEOUT_S = 300.0  # five minutes: the host reads the code out, the partner types it in (Tucker, 2026-10-22)
RELAY_AFTER_S = 6.0  # punching this long without a reply: both go through the relay (M14)


def default_relays():
    """Relays to fall back on (link/relay.py: anyone's): COOP_RELAYS="host:port,host:port"."""
    out = []
    for item in os.environ.get("COOP_RELAYS", "").split(","):
        host, _, port = item.strip().rpartition(":")
        if host and port.isdigit():
            out.append((host, int(port)))
    return out


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
        # Android: the CA file android/main.py makes from the system's (its Python doesn't read
        # SSL_CERT_FILE itself); elsewhere, the system's
        self._tls = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)
        self._msgs = {}
        self._subs = set()
        self._lock = threading.Lock()
        self._closed = False
        self.post_error = self.read_error = None  # the last failure, until a request works again

    @property
    def error(self):
        """Why the relay can't be reached right now, or None."""
        return self.post_error or self.read_error

    def close(self):
        """Stops reading (the connector found the partner, or gave up)."""
        self._closed = True

    def publish(self, topic, msg):
        def post():
            try:
                req = urllib.request.Request(f"{self.URL}/{topic}", data=json.dumps(msg).encode(), method="POST")
                urllib.request.urlopen(req, timeout=5, context=self._tls).read()
                self.post_error = None
            except Exception as e:  # noqa: BLE001 - offline or blocked: the lobby says so, the connector retries
                self.post_error = repr(e)
                log.warning("relay: posting failed: %r", e)
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
        while not self._closed:
            try:
                with urllib.request.urlopen(f"{self.URL}/{topic}/json?since={since}", timeout=60, context=self._tls) as resp:
                    self.read_error = None
                    for line in resp:
                        if self._closed:
                            return
                        outer = json.loads(line)
                        if outer.get("event") == "message":
                            since = outer.get("id", since)
                            try:
                                msg = json.loads(outer.get("message", ""))
                            except ValueError:
                                continue
                            with self._lock:
                                self._msgs[topic].append(msg)
            except Exception as e:  # noqa: BLE001 - dropped or timed out: reconnect
                if not isinstance(e, TimeoutError):
                    self.read_error = repr(e)
                    log.warning("relay: reading failed: %r", e)
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
                 lan_ip=None, timeout=TIMEOUT_S, resolve=True, version=None, relays=None, portmap=None):
        """role: "host" or "join". hello: () -> the HELO payload to punch with. version: {"link":
        wire version, "app": the launcher's}, posted with the candidates, so that two different
        versions are told so at once, instead of waiting for packets that can't be understood."""
        self.t, self.room, self.role, self.relay, self.hello = transport, room, role, relay, hello
        self.topic = room_topic(room)
        self.lan_ip = lan_ip
        self.timeout = timeout
        self.version = version or {}
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
        self._broadcast_at = None
        self._broadcasts = []
        self._resolve = resolve
        self._servers = list(stun_servers)
        self.relays = list(default_relays() if relays is None else relays)  # M14: the last step
        self.via = None          # the relay both use, once it comes to that
        self._their_relay = None  # the host's choice, from its message
        self._punch_t0 = None
        # M14 step 3: ask the router to open the game's port (UPnP, NAT-PMP), in the background;
        # portmap(port) -> (public ip, port) or None (tests: link/natsim's routers)
        self.mapped = None
        self._mapping = None
        if portmap is None and not os.environ.get("COOP_NO_PORTMAP"):
            from .portmap import map_port
            portmap = lambda port: map_port(port, lan_ip=lan_ip)  # noqa: E731
        if portmap is not None:
            self._mapping = threading.Thread(target=lambda: setattr(self, "mapped", portmap(transport.port)),
                                             daemon=True)
            self._mapping.start()
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
        left = None if self._t0 is None else max(0, int(self.timeout - (self.t.clock() - self._t0)))
        return {"state": self.state, "reason": self.reason, "nat": self.nat, "their_nat": self.their_nat,
                "via": self.via, "mapped": self.mapped,
                "mine": self.mine, "theirs": self.theirs, "left_s": left,
                "relay_error": getattr(self.relay, "error", None)}

    def _done(self, state):
        self.state = state
        close = getattr(self.relay, "close", None)
        if close:
            close()
        return state

    def tick(self):
        if self.state in ("connected", "failed"):
            return self.state
        now = self.t.clock()
        if self._t0 is None:
            self._t0 = now
        if self.t.peer is not None and self.t.peer_confirmed:
            log.info("connect %s: connected to %s after %.1f s", self.role, self.t.peer, now - self._t0)
            return self._done("connected")
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
                ip = self.lan_ip or self.t.sock.getsockname()[0]
                if ip in ("0.0.0.0", ""):  # listening everywhere: the address the LAN knows us by
                    from .rendezvous import local_ip
                    ip = local_ip()
                lan = (ip, self.t.port)
                self.mine = [list(lan)] + [list(p) for p in public if p != lan]
                # the LAN broadcast: everywhere on this network, and this /24's own broadcast address
                # (some routers don't pass 255.255.255.255 between Wi-Fi and wired)
                self._broadcasts = [("255.255.255.255", GAME_PORT), (ip.rsplit(".", 1)[0] + ".255", GAME_PORT)]
                try:
                    self.t.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                except OSError:
                    self._broadcasts = []
                self.state = "waiting"
                log.info("connect %s: my addresses %s (router: %s); waiting for the partner on the relay",
                         self.role, self.mine, self.nat)
        # the router opened our port: that address first, and posted again
        if self.mapped and self.state != "starting" and list(self.mapped) not in self.mine:
            self.mine.insert(0, list(self.mapped))
            self._published = None
            log.info("connect %s: the router opened %s for us", self.role, self.mapped)
        # 2. rendezvous
        if self.state in ("waiting", "punching"):
            every = RETRY_S if getattr(self.relay, "post_error", None) else REPUBLISH_S
            if self._published is None or now - self._published > every:
                msg = {"role": self.role, "nonce": self.nonce, "cands": self.mine,
                       "nat": self.nat, "token": room_token(self.room), "ver": self.version}
                if self.role == "host" and self.relays:  # the host picks the relay both will use
                    msg["relay"] = list(self.relays[0])
                self.relay.publish(self.topic, msg)
                self._published = now
            other = "join" if self.role == "host" else "host"
            msgs = [m for m in self.relay.poll(self.topic)
                    if m.get("role") == other and m.get("token") == room_token(self.room)]
            if msgs:
                newest = max(msgs, key=lambda m: m.get("nonce", 0))
                theirs = newest.get("ver") or {}  # none: a version from before 0.9.0
                if self.version.get("link") is not None and theirs.get("link") != self.version["link"]:
                    self._done("failed")
                    log.warning("connect %s: partner's version %s, mine %s", self.role, theirs, self.version)
                    self.reason = (f"Your partner has {'SOTN Co-op ' + theirs['app'] if theirs.get('app') else 'an older SOTN Co-op'}, "
                                   f"and you have {self.version.get('app') or 'another version'}. Both of you need the "
                                   "same version: whoever has the older one, install the newer one, then try again.")
                    return self.state
                if newest.get("relay"):
                    self._their_relay = tuple(newest["relay"])
                cands = [tuple(c) for c in newest.get("cands", []) if len(c) == 2]
                if cands != self.theirs:
                    self.theirs, self.their_nat = cands, newest.get("nat")
                    log.info("connect %s: partner's addresses %s (router: %s, version %s); punching",
                             self.role, cands, self.their_nat, theirs.get("app"))
                self.state = "punching"
        # 3. punching, and after RELAY_AFTER_S without a reply, the relay (M14)
        if self.state == "punching" and self._punch_t0 is None:
            self._punch_t0 = now
        if (self.state == "punching" and self.via is None and now - self._punch_t0 > RELAY_AFTER_S
                and (self._their_relay or (self.role == "host" and self.relays))):
            self.via = self._their_relay or self.relays[0]
            self.t.use_relay(self.via, room_token(self.room))
            log.info("connect %s: no direct path after %.0f s; through the relay %s", self.role, RELAY_AFTER_S, self.via)
        if self.state == "punching" and now - self._punched >= PUNCH_EVERY_S:
            self._punched = now
            for c in self.theirs + ([self.via] if self.via else []):
                self.t.probe(c, TAG_HELLO, self.hello())
        # 4. the LAN broadcast (needs no relay)
        if self._broadcasts and (self._broadcast_at is None or now - self._broadcast_at >= BROADCAST_EVERY_S):
            self._broadcast_at = now
            for c in self._broadcasts:
                self.t.probe(c, TAG_HELLO, self.hello())
        if now - self._t0 > self.timeout:
            self.reason = self._why()
            self._done("failed")
            log.warning("connect %s: gave up (%s): %s", self.role, self.state, self.reason)
        return self.state

    def _why(self):
        if not self.theirs and getattr(self.relay, "error", None):
            return ("Couldn't reach the room-code server (ntfy.sh), so your partner's game couldn't be "
                    "found. Check this device's internet connection. On the same Wi-Fi, ask your "
                    "partner to host and join with the ip:port it shows in Help ▸ About.")
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
