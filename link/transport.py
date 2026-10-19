"""Messages between the two hosts: UDP datagrams, on localhost now and across a network later.
Presence is state, not a stream of events, so a lost or late datagram only costs freshness."""

import socket
import struct

_HEADER = struct.Struct("<4sI")  # tag, sequence number
TAG_PRESENCE = b"PRES"


class UdpTransport:
    """port 0 binds any free port (see .port); the peer can be set later with connect()."""

    def __init__(self, port=0, peer_port=None, host="127.0.0.1"):
        self.host = host
        self.peer = (host, peer_port) if peer_port else None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.seq = 0

    def connect(self, peer_port):
        self.peer = (self.host, peer_port)

    def send(self, tag, payload):
        if self.peer is None:
            return
        self.seq += 1
        try:
            self.sock.sendto(_HEADER.pack(tag, self.seq) + payload, self.peer)
        except OSError:  # partner not listening (yet, or any more): presence is best-effort
            pass

    def receive(self):
        """All datagrams waiting right now, as (tag, seq, payload), oldest first."""
        out = []
        while True:
            try:
                data = self.sock.recv(65536)
            except (BlockingIOError, ConnectionRefusedError):
                return out
            if len(data) >= _HEADER.size:
                tag, seq = _HEADER.unpack_from(data)
                out.append((tag, seq, data[_HEADER.size:]))

    def close(self):
        self.sock.close()
