"""Connect codes, STUN parsing, and direct-IP parsing (design/M7, D74; finding the partner: link/connect.py).

Three ways to connect, all using the same Join box:
1. A room code (e.g. BAT-7K2Q): both players meet on a public, account-free relay (ntfy.sh)
   and hole-punch (link/connect.py).
2. A 10-character stateless endpoint code (e.g. K7M2-9P4Q-W3): encodes (ip, port) + a 2-bit
   checksum in base32. Needs zero servers of any kind once STUN/LAN knows the address.
3. Direct IP and port (e.g. 192.168.1.42:54321 or :54321 for localhost).
"""

import os
import random
import re
import socket
import struct
import zlib

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 chars, no 0/O/1/I
_DECODE = {c: i for i, c in enumerate(ALPHABET)}
ROOM_WORDS = ("BAT", "FOG", "ORB", "OWL", "AXE", "KEY", "CAT", "SUN", "GEM", "ROD", "URN", "IMP")
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
        raise ConnectError("A connect code is 10 characters (like K7M2-9P4Q-W3); a room code looks like BAT-7K2Q.")
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
    """A room code like BAT-7K2Q: a word and four characters (12.6 million codes), easy to read
    out loud, and never 0/O or 1/I."""
    r = rng or random
    return f"{r.choice(ROOM_WORDS)}-{''.join(r.choice(ALPHABET) for _ in range(4))}"


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
    if len(clean) == 7 and clean[:3] in ROOM_WORDS:
        bad = [c for c in clean[3:] if c not in _DECODE]
        if bad:
            raise ConnectError(f"'{bad[0]}' isn't used in room codes (0, O, 1 and I never are). Check for a typo.")
        return "room", f"{clean[:3]}-{clean[3:]}"
    if len(clean) == 10:
        return "endpoint", decode_endpoint(clean)
    raise ConnectError(
        "Didn't recognize that code. Enter a room code (like BAT-7K2Q), "
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
