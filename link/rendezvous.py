"""Zero-infrastructure connect codes, STUN/UPnP discovery, and direct-IP parsing (design/M7, D74).

Three ways to connect, all using the same Join box:
1. A 6-character room code (e.g. BAT-429): exchanged over local LAN UDP broadcast and a public
   zero-account HTTPS relay (ntfy.sh), so both players learn each other's endpoints and hole-punch.
2. A 10-character stateless endpoint code (e.g. K7M2-9P4Q-W3): encodes (ip, port) + a 2-bit
   checksum in base32. Needs zero servers of any kind once STUN/LAN knows the address.
3. Direct IP and port (e.g. 192.168.1.42:54321 or :54321 for localhost).
"""

import hashlib
import json
import os
import random
import re
import socket
import struct
import threading
import time
import urllib.request
import zlib

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 chars, no 0/O/1/I
_DECODE = {c: i for i, c in enumerate(ALPHABET)}
ROOM_WORDS = ("BAT", "FOG", "ORB", "OWL", "AXE", "KEY", "CAT", "SUN", "GEM", "ROD", "URN", "IMP")
STUN_SERVERS = (
    ("stun.l.google.com", 19302),
    ("stun.cloudflare.com", 3478),
    ("stun.nextcloud.com", 443),
)
LAN_PORTS = (45671, 45672, 45673)
MAGIC_COOKIE = 0x2112A442


class ConnectError(Exception):
    """Plain-words error shown to the player when a connect code or IP is invalid."""


def encode_endpoint(ip, port):
    """Encodes an IPv4 address and UDP port into a 10-char base32 connect code (XXXX-XXXX-XX)."""
    try:
        raw_ip = socket.inet_aton(ip)
    except OSError as e:
        raise ConnectError(f"'{ip}' isn't a valid IPv4 address.") from e
    if not (1 <= int(port) <= 65535):
        raise ConnectError(f"Port {port} must be between 1 and 65535.")
    raw = raw_ip + struct.pack(">H", int(port))
    chk = zlib.crc32(raw) & 0x03
    val = (int.from_bytes(raw, "big") << 2) | chk
    chars = []
    for _ in range(10):
        chars.append(ALPHABET[val & 0x1F])
        val >>= 5
    s = "".join(reversed(chars))
    return f"{s[:4]}-{s[4:8]}-{s[8:]}"


def decode_endpoint(code):
    """Decodes a 10-char base32 connect code back into (ip, port). Raises ConnectError on typos."""
    clean = re.sub(r"[\s\-_]", "", code.upper())
    if len(clean) != 10:
        raise ConnectError("A connect code is 10 characters (like K7M2-9P4Q-W3), or 6 for a room code (like BAT-429).")
    val = 0
    for ch in clean:
        if ch not in _DECODE:
            raise ConnectError(f"'{ch}' isn't used in connect codes (0, O, 1 and I are never used). Check for a typo.")
        val = (val << 5) | _DECODE[ch]
    chk = val & 0x03
    raw = (val >> 2).to_bytes(6, "big")
    if (zlib.crc32(raw) & 0x03) != chk:
        raise ConnectError("That connect code has a typo (checksum didn't match). Check the characters and try again.")
    ip = socket.inet_ntoa(raw[:4])
    port = struct.unpack(">H", raw[4:6])[0]
    if port == 0:
        raise ConnectError("That connect code has port 0, which isn't valid.")
    return ip, port


def make_room_code(rng=None):
    """Generates a short 6-character room code like BAT-429."""
    r = rng or random
    word = r.choice(ROOM_WORDS)
    num = r.randint(100, 999)
    return f"{word}-{num}"


def parse_connect_input(text):
    """Parses user input into ('direct', (ip, port)), ('endpoint', (ip, port)), or ('room', 'XXX-999')."""
    s = (text or "").strip()
    if not s:
        raise ConnectError("Enter your partner's connect code or IP:port.")
    if ":" in s:
        host, port_s = s.rsplit(":", 1)
        host = host.strip() or "127.0.0.1"
        try:
            port = int(port_s.strip())
        except ValueError as e:
            raise ConnectError(f"'{port_s}' isn't a valid port number.") from e
        if not (1 <= port <= 65535):
            raise ConnectError(f"Port {port} must be between 1 and 65535.")
        try:
            socket.inet_aton(host)
        except OSError as e:
            raise ConnectError(f"'{host}' isn't a valid IPv4 address.") from e
        return "direct", (host, port)
    clean = re.sub(r"[\s\-_]", "", s.upper())
    if len(clean) == 6 and clean[:3].isalpha() and clean[3:].isdigit():
        return "room", f"{clean[:3]}-{clean[3:]}"
    if len(clean) == 10:
        return "endpoint", decode_endpoint(clean)
    raise ConnectError(
        "Didn't recognize that code. Enter a 6-character room code (BAT-429), "
        "a 10-character connect code (K7M2-9P4Q-W3), or IP:port (192.168.1.10:54321)."
    )


def local_ip():
    """The machine's primary LAN IPv4 address, or 127.0.0.1."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def stun_public_endpoint(local_port=0, timeout=1.2):
    """Queries public STUN servers (RFC 5389) from a fresh UDP socket or bound port.
    Returns (public_ip, public_port) or None if offline/blocked."""
    tx_id = os.urandom(12)
    req = struct.pack(">HHI12s", 0x0001, 0, MAGIC_COOKIE, tx_id)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout / max(1, len(STUN_SERVERS)))
        if local_port:
            try:
                sock.bind(("0.0.0.0", local_port))
            except OSError:
                pass
        for host, port in STUN_SERVERS:
            try:
                sock.sendto(req, (host, port))
                data, _ = sock.recvfrom(2048)
            except OSError:
                continue
            parsed = _parse_stun_response(data, tx_id)
            if parsed:
                return parsed
    return None


def _parse_stun_response(data, tx_id):
    if len(data) < 20:
        return None
    msg_type, msg_len, cookie, rx_tx = struct.unpack_from(">HHI12s", data)
    if msg_type != 0x0101 or cookie != MAGIC_COOKIE or rx_tx != tx_id:
        return None
    pos = 20
    end = min(len(data), 20 + msg_len)
    while pos + 4 <= end:
        attr_type, attr_len = struct.unpack_from(">HH", data, pos)
        val = data[pos + 4:pos + 4 + attr_len]
        pos += 4 + ((attr_len + 3) & ~3)
        if attr_type == 0x0020 and len(val) >= 8 and val[1] == 0x01:  # XOR-MAPPED-ADDRESS (IPv4)
            xport = struct.unpack_from(">H", val, 2)[0] ^ (MAGIC_COOKIE >> 16)
            xip = struct.unpack_from(">I", val, 4)[0] ^ MAGIC_COOKIE
            return socket.inet_ntoa(struct.pack(">I", xip)), xport
        if attr_type == 0x0001 and len(val) >= 8 and val[1] == 0x01:  # MAPPED-ADDRESS (IPv4)
            port = struct.unpack_from(">H", val, 2)[0]
            ip = socket.inet_ntoa(val[4:8])
            return ip, port
    return None


def _room_topic(code):
    clean = re.sub(r"[\s\-_]", "", code.upper())
    digest = hashlib.sha256(f"sotn-coop-v1:{clean}".encode()).hexdigest()[:20]
    return f"sotn-coop-{digest}"


class RoomResponder:
    """Runs in the background while the Host Online screen is waiting for a partner.
    Answers 6-character room-code lookups over local/LAN UDP and public HTTPS relay."""

    def __init__(self, room_code, endpoint, wan_endpoint=None, relay=True):
        self.room_code = re.sub(r"[\s\-_]", "", room_code.upper())
        self.endpoint = (str(endpoint[0]), int(endpoint[1]))
        self.wan_endpoint = (str(wan_endpoint[0]), int(wan_endpoint[1])) if wan_endpoint else None
        self.relay = relay
        self.joiner_endpoint = None
        self._stop = threading.Event()
        self._socks = []
        for p in LAN_PORTS:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", p))
                s.setblocking(False)
                self._socks.append(s)
            except OSError:
                pass
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _payload(self):
        return json.dumps({
            "role": "host",
            "room": self.room_code,
            "lan": list(self.endpoint),
            "wan": list(self.wan_endpoint or self.endpoint),
        }).encode()

    def _run(self):
        topic = _room_topic(self.room_code)
        if self.relay:
            threading.Thread(target=self._publish_relay, args=(topic,), daemon=True).start()
        while not self._stop.is_set():
            for s in self._socks:
                while True:
                    try:
                        data, addr = s.recvfrom(2048)
                    except OSError:
                        break
                    try:
                        msg = json.loads(data.decode())
                    except ValueError:
                        continue
                    if msg.get("room") == self.room_code and msg.get("role") == "join":
                        join_ep = msg.get("lan") or [addr[0], addr[1]]
                        self.joiner_endpoint = (str(join_ep[0]), int(join_ep[1]))
                        try:
                            s.sendto(self._payload(), addr)
                        except OSError:
                            pass
            time.sleep(0.03)

    def _publish_relay(self, topic):
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=self._payload(), method="POST")
            urllib.request.urlopen(req, timeout=2.5).read()
        except Exception:  # noqa: BLE001 - offline or blocked: LAN and endpoint code still work
            pass

    def close(self):
        self._stop.set()
        for s in self._socks:
            try:
                s.close()
            except OSError:
                pass


def resolve_room_code(room_code, my_endpoint=("127.0.0.1", 0), timeout=3.0, relay=True):
    """Finds the host's (ip, port) for a 6-character room code via local/LAN UDP or public relay."""
    clean = re.sub(r"[\s\-_]", "", room_code.upper())
    probe = json.dumps({"role": "join", "room": clean, "lan": [str(my_endpoint[0]), int(my_endpoint[1])]}).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setblocking(False)
        deadline = time.monotonic() + timeout
        relay_checked = not relay
        while time.monotonic() < deadline:
            for p in LAN_PORTS:
                for target in ("127.0.0.1", "255.255.255.255"):
                    try:
                        s.sendto(probe, (target, p))
                    except OSError:
                        pass
            time.sleep(0.05)
            while True:
                try:
                    data, _ = s.recvfrom(2048)
                except OSError:
                    break
                try:
                    msg = json.loads(data.decode())
                except ValueError:
                    continue
                if msg.get("room") == clean and msg.get("role") == "host":
                    ep = msg.get("lan") or msg.get("wan")
                    if ep and len(ep) == 2:
                        return str(ep[0]), int(ep[1])
            if not relay_checked:
                relay_checked = True
                ep = _poll_relay(_room_topic(clean))
                if ep:
                    return ep
    raise ConnectError(f"Couldn't find an active game for room code {room_code}. Check the code or use the 10-character connect code.")


def _poll_relay(topic):
    try:
        url = f"https://ntfy.sh/{topic}/json?poll=1&since=10m"
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            lines = resp.read().decode("utf-8", errors="replace").splitlines()
        for line in reversed(lines):
            outer = json.loads(line)
            if outer.get("event") == "message" and outer.get("message"):
                msg = json.loads(outer["message"])
                if msg.get("role") == "host":
                    ep = msg.get("wan") or msg.get("lan")
                    if ep and len(ep) == 2:
                        return str(ep[0]), int(ep[1])
    except Exception:  # noqa: BLE001
        pass
    return None
