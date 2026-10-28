"""The relay (design/M14-relay.md): the last step when two games can't reach each other directly
(symmetric routers on both sides, or against a port-restricted one). Open source, one file, run by
anyone: a player's launcher (a setting), or anyone's server:

    python -m link.relay [--port 3479] [--max-rooms 64]

A game sends it `RLY1` + room id (8 bytes) + an encrypted packet. The relay keeps, per room id, the
two addresses that sent last, and forwards each packet to the other one. It never sees the room
code: the room id is a hash of it, and the packets are encrypted with a key from the code
(`seal`/`open_`, used by link/transport.py), so it can't read or change them. Rooms idle for a
minute are forgotten; a room's traffic is capped, and so is the number of rooms."""

import argparse
import hashlib
import hmac
import os
import socket
import struct
import time

MAGIC = b"RLY1"
HEADER = len(MAGIC) + 8
IDLE_S = 60.0
MAX_ROOMS = 64
ROOM_BYTES_PER_S = 200_000  # about 1.6 Mbit/s a room: a game pair uses about 250 kbit/s each way
PORT = 3479


def room_id(code_token):
    """The room's id at the relay, from the room token (link/connect.room_token)."""
    return hashlib.sha256(b"sotn-coop-relay-id:" + code_token.encode()).digest()[:8]


def _key(code_token):
    return hashlib.sha256(b"sotn-coop-relay-key:" + code_token.encode()).digest()


def _stream(key, nonce, n):
    out = bytearray()
    block = 0
    while len(out) < n:
        out += hashlib.sha256(key + nonce + struct.pack("<I", block)).digest()
        block += 1
    return bytes(out[:n])


def seal(code_token, packet):
    """An encrypted, authenticated packet for the relay to carry: nonce (8), tag (8), ciphertext."""
    key, nonce = _key(code_token), os.urandom(8)
    body = bytes(a ^ b for a, b in zip(packet, _stream(key, nonce, len(packet))))
    tag = hmac.new(key, nonce + body, hashlib.sha256).digest()[:8]
    return nonce + tag + body


def open_(code_token, sealed):
    """The packet, or None if it wasn't sealed with this room's key (or was changed on the way)."""
    if len(sealed) < 16:
        return None
    key, nonce, tag, body = _key(code_token), sealed[:8], sealed[8:16], sealed[16:]
    if not hmac.compare_digest(tag, hmac.new(key, nonce + body, hashlib.sha256).digest()[:8]):
        return None
    return bytes(a ^ b for a, b in zip(body, _stream(key, nonce, len(body))))


class Relay:
    """Forwards between the two addresses of each room id. `sock`: a bound UDP socket (or
    link/natsim's virtual one); `clock`: seconds."""

    def __init__(self, sock, clock=time.monotonic, max_rooms=MAX_ROOMS):
        self.sock, self.clock, self.max_rooms = sock, clock, max_rooms
        self.rooms = {}  # room id -> {"addrs": [(addr, last seen)], "budget": bytes, "at": time}
        self.forwarded = self.dropped = 0

    def handle(self, data, addr):
        if len(data) < HEADER or data[:len(MAGIC)] != MAGIC:
            self.dropped += 1
            return
        now = self.clock()
        rid = data[len(MAGIC):HEADER]
        room = self.rooms.get(rid)
        if room is None:
            self._expire(now)
            if len(self.rooms) >= self.max_rooms:
                self.dropped += 1
                return
            room = self.rooms[rid] = {"addrs": [], "budget": ROOM_BYTES_PER_S, "at": now}
        room["budget"] = min(ROOM_BYTES_PER_S, room["budget"] + (now - room["at"]) * ROOM_BYTES_PER_S)
        room["at"] = now
        addrs = [(a, t) for a, t in room["addrs"] if a != addr and now - t < IDLE_S]
        room["addrs"] = (addrs + [(addr, now)])[-2:]  # this room's two games, newest kept
        if len(data) == HEADER:  # a keepalive: registers only
            return
        if room["budget"] < len(data):
            self.dropped += 1
            return
        for other, _ in room["addrs"]:
            if other != addr:
                room["budget"] -= len(data)
                self.forwarded += 1
                try:
                    self.sock.sendto(data, other)
                except OSError:
                    pass

    def _expire(self, now):
        for rid in [r for r, room in self.rooms.items() if now - room["at"] > IDLE_S]:
            del self.rooms[rid]

    def poll(self):
        """Handles everything waiting on the socket (non-blocking)."""
        while True:
            try:
                data, addr = self.sock.recvfrom(65536)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                return
            self.handle(data, (str(addr[0]), int(addr[1])))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--max-rooms", type=int, default=MAX_ROOMS)
    args = ap.parse_args()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    relay = Relay(sock, max_rooms=args.max_rooms)
    print(f"SOTN Co-op relay on UDP {args.port}", flush=True)
    sock.setblocking(True)
    while True:
        data, addr = sock.recvfrom(65536)
        relay.handle(data, (str(addr[0]), int(addr[1])))


if __name__ == "__main__":
    main()
