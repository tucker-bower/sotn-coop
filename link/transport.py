"""Messages between the two hosts: UDP datagrams, on localhost now and across a network later.

Presence is state, not a stream of events, so a lost or late datagram only costs freshness.
Progression events must arrive exactly once and in order: ReliableChannel adds sequence
numbers, cumulative acks and resends on top of the same socket."""

import socket
import struct

_HEADER = struct.Struct("<4sI")  # tag, sequence number
TAG_PRESENCE = b"PRES"
TAG_EVENTS = b"EVTS"  # payload: first seq (u32), then events
TAG_ACK = b"ACK "     # payload: highest seq delivered in order (u32)
TAG_SNAP = b"SNAP"    # payload: a shared-room snapshot (state: only the newest matters)


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
        self.partitioned = False  # tests: drop everything both ways, like a dead network

    def connect(self, peer_port):
        self.peer = (self.host, peer_port)

    def send(self, tag, payload):
        if self.peer is None or self.partitioned:
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
            if len(data) >= _HEADER.size and not self.partitioned:
                tag, seq = _HEADER.unpack_from(data)
                out.append((tag, seq, data[_HEADER.size:]))

    def close(self):
        self.sock.close()


class ReliableChannel:
    """Exactly-once, in-order delivery of fixed-size records over a UdpTransport.

    The sender keeps every record until the peer acks it and resends the unacked tail every
    `resend_every` ticks; the receiver delivers in sequence order and drops duplicates.
    Call tick() once per frame with the datagrams of interest."""

    MAX_PER_DATAGRAM = 128

    def __init__(self, transport, record_size, resend_every=15):
        self.t, self.size, self.resend_every = transport, record_size, resend_every
        self.next_seq = 1           # seq of the next record we queue
        self.unacked = []           # [(seq, record)]
        self.delivered = 0          # highest seq delivered to us in order
        self.early = {}             # seq -> record, received ahead of a gap
        self._since_send = 0
        self._ack_due = False

    def queue(self, records):
        for r in records:
            self.unacked.append((self.next_seq, r))
            self.next_seq += 1
        if records:
            self._send_unacked()

    def _send_unacked(self):
        self._since_send = 0
        for i in range(0, len(self.unacked), self.MAX_PER_DATAGRAM):
            chunk = self.unacked[i:i + self.MAX_PER_DATAGRAM]
            self.t.send(TAG_EVENTS, struct.pack("<I", chunk[0][0]) + b"".join(r for _, r in chunk))

    def tick(self, datagrams):
        """Handles this frame's EVTS/ACK datagrams; returns newly delivered records, in order."""
        out = []
        for tag, _, payload in datagrams:
            if tag == TAG_ACK:
                acked = struct.unpack_from("<I", payload)[0]
                self.unacked = [(s, r) for s, r in self.unacked if s > acked]
            elif tag == TAG_EVENTS:
                first = struct.unpack_from("<I", payload)[0]
                body = payload[4:]
                for i in range(len(body) // self.size):
                    seq = first + i
                    if seq > self.delivered:
                        self.early[seq] = body[i * self.size:(i + 1) * self.size]
                self._ack_due = True
        while self.delivered + 1 in self.early:
            self.delivered += 1
            out.append(self.early.pop(self.delivered))
        if self._ack_due:
            self.t.send(TAG_ACK, struct.pack("<I", self.delivered))
            self._ack_due = False
        self._since_send += 1
        if self.unacked and self._since_send >= self.resend_every:
            self._send_unacked()
        return out

