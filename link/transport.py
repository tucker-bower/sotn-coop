"""Messages between the two hosts: UDP datagrams, on localhost now and across a network later.

Presence is state, not a stream of events, so a lost or late datagram only costs freshness.
Progression events must arrive exactly once and in order: ReliableChannel adds sequence
numbers, cumulative acks and resends on top of the same socket.
Shared-room snapshots (SNAP) are compressed with zlib and split into MTU-safe chunks (SNPC,
<= 1200 bytes per UDP packet) so routers never drop IP-fragmented UDP packets online (D74)."""

import random
import socket
import struct
import time
import zlib

_HEADER = struct.Struct("<4sI")  # tag, sequence number
TAG_PRESENCE = b"PRES"
TAG_EVENTS = b"EVTS"  # payload: first seq (u32), then events
TAG_ACK = b"ACK "     # payload: highest seq delivered in order (u32)
TAG_SNAP = b"SNAP"    # payload: a shared-room snapshot (state: only the newest matters)
TAG_SNPC = b"SNPC"    # payload: snap_id (u32), chunk_idx (u8), chunk_cnt (u8), zlib chunk
TAG_CTRL = b"CTRL"    # payload: seq (u32), last (u8), pad (u8), len (u16), chunk (reliable control/save)
TAG_CACK = b"CACK"    # payload: highest CTRL seq delivered in order (u32)
TAG_HELLO = b"HELO"   # payload: JSON {"link": version, "patch": target CRC32 or null}, once a second

_SNPC_HDR = struct.Struct("<IBB")
_CTRL_HDR = struct.Struct("<IBBH")
MAX_SNAP_CHUNK = 1150  # keeps total UDP payload <= 1164 bytes (well below 1200-byte path MTU)
MAX_CTRL_CHUNK = 1000


class UdpTransport:
    """port 0 binds any free port (see .port); the peer can be set later with connect()."""

    def __init__(self, port=0, peer_port=None, host="127.0.0.1", bind_host=None):
        self.host = host
        self.peer = None
        if peer_port is not None:
            self.connect(peer_port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((bind_host or host, port))
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.seq = 0
        self.partitioned = False  # tests: drop everything both ways, like a dead network
        self.learn_peer = False   # online: update peer address from authenticated incoming traffic
        self.last_rx_time = None
        # Snapshot compression & MTU chunking (D74)
        self._snap_id = 0
        self._snap_parts = {}     # snap_id -> {chunk_idx: bytes, "_cnt": chunk_cnt}
        self._snap_done = 0       # highest snap_id reassembled
        self.max_packet_sent = 0
        # Simulated WAN conditions for harness tests (set_wan)
        self.mtu = 0              # if > 0, drop any UDP payload > self.mtu bytes
        self.mtu_drops = 0
        self.loss = 0.0           # fraction of packets randomly dropped (0.0 - 1.0)
        self.loss_drops = 0
        self.latency_ms = 0       # one-way delay in ms
        self._rng = random.Random(1)
        self._delayed = []        # [(deliver_at, packet_bytes, peer)]

    def connect(self, peer):
        """peer: port (int), (host, port) tuple/list, or 'host:port' string."""
        if isinstance(peer, int):
            self.peer = (self.host, peer)
        elif isinstance(peer, (tuple, list)) and len(peer) == 2:
            self.peer = (str(peer[0]), int(peer[1]))
        elif isinstance(peer, str) and ":" in peer:
            h, p = peer.rsplit(":", 1)
            self.peer = (h.strip() or self.host, int(p))
        else:
            self.peer = None

    def set_wan(self, mtu=0, loss=0.0, latency_ms=0, seed=1):
        """Configures simulated WAN limits (MTU cap, packet loss, latency) for harness testing."""
        self.mtu = int(mtu)
        self.loss = float(loss)
        self.latency_ms = float(latency_ms)
        self._rng = random.Random(seed)
        return True

    def wan_stats(self):
        return {
            "max_packet_sent": self.max_packet_sent,
            "mtu_drops": self.mtu_drops,
            "loss_drops": self.loss_drops,
        }

    def _flush_delayed(self):
        if not self._delayed:
            return
        now = time.monotonic()
        still = []
        for deliver_at, pkt, peer in self._delayed:
            if now >= deliver_at:
                try:
                    self.sock.sendto(pkt, peer)
                except OSError:
                    pass
            else:
                still.append((deliver_at, pkt, peer))
        self._delayed = still

    def _send_datagram(self, tag, payload):
        if self.peer is None or self.partitioned:
            return
        self.seq += 1
        pkt = _HEADER.pack(tag, self.seq) + payload
        if len(pkt) > self.max_packet_sent:
            self.max_packet_sent = len(pkt)
        if self.mtu and len(pkt) > self.mtu:
            self.mtu_drops += 1
            return
        if self.loss > 0.0 and self._rng.random() < self.loss:
            self.loss_drops += 1
            return
        if self.latency_ms > 0:
            self._delayed.append((time.monotonic() + self.latency_ms / 1000.0, pkt, self.peer))
            self._flush_delayed()
            return
        try:
            self.sock.sendto(pkt, self.peer)
        except OSError:  # partner not listening (yet, or any more): presence is best-effort
            pass

    def send(self, tag, payload):
        self._flush_delayed()
        if self.peer is None or self.partitioned:
            return
        if tag == TAG_SNAP:
            comp = zlib.compress(payload, level=1)
            self._snap_id = (self._snap_id + 1) & 0xFFFFFFFF
            chunks = [comp[i:i + MAX_SNAP_CHUNK] for i in range(0, max(1, len(comp)), MAX_SNAP_CHUNK)]
            cnt = len(chunks)
            for idx, chunk in enumerate(chunks):
                self._send_datagram(TAG_SNPC, _SNPC_HDR.pack(self._snap_id, idx, cnt) + chunk)
            return
        self._send_datagram(tag, payload)

    def receive(self):
        """All datagrams waiting right now, as (tag, seq, payload), oldest first."""
        self._flush_delayed()
        out = []
        while True:
            try:
                data, addr = self.sock.recvfrom(65536)
            except (BlockingIOError, ConnectionRefusedError, OSError):
                return out
            if len(data) < _HEADER.size or self.partitioned:
                continue
            tag, seq = _HEADER.unpack_from(data)
            body = data[_HEADER.size:]
            if self.learn_peer and tag in (TAG_HELLO, TAG_PRESENCE, TAG_EVENTS, TAG_ACK, TAG_SNAP, TAG_SNPC, TAG_CTRL, TAG_CACK):
                self.peer = addr
            self.last_rx_time = time.monotonic()
            if tag == TAG_SNPC and len(body) >= _SNPC_HDR.size:
                snap_id, idx, cnt = _SNPC_HDR.unpack_from(body)
                if snap_id <= self._snap_done or cnt == 0 or idx >= cnt:
                    continue
                bucket = self._snap_parts.setdefault(snap_id, {"_cnt": cnt})
                bucket[idx] = body[_SNPC_HDR.size:]
                if len(bucket) - 1 == bucket["_cnt"]:
                    comp = b"".join(bucket[i] for i in range(bucket["_cnt"]))
                    self._snap_done = snap_id
                    for old_id in [k for k in self._snap_parts if k <= snap_id]:
                        del self._snap_parts[old_id]
                    try:
                        raw = zlib.decompress(comp)
                    except zlib.error:
                        continue
                    out.append((TAG_SNAP, seq, raw))
                elif len(self._snap_parts) > 4:
                    oldest = min(self._snap_parts)
                    del self._snap_parts[oldest]
            else:
                out.append((tag, seq, body))

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


class ReliableMessages:
    """Reliable, ordered delivery of arbitrary byte blobs (e.g. online joint saves) over UdpTransport.
    Blobs are zlib-compressed and split into <= MAX_CTRL_CHUNK pieces so every packet stays MTU-safe."""

    def __init__(self, transport, resend_every=15):
        self.t, self.resend_every = transport, resend_every
        self.next_seq = 1
        self.unacked = []     # [(seq, last, chunk)]
        self.delivered = 0
        self.early = {}       # seq -> (last, chunk)
        self._rx_buf = bytearray()
        self._since_send = 0
        self._ack_due = False

    def send(self, blob):
        comp = zlib.compress(blob, level=6)
        chunks = [comp[i:i + MAX_CTRL_CHUNK] for i in range(0, max(1, len(comp)), MAX_CTRL_CHUNK)]
        for i, chunk in enumerate(chunks):
            last = 1 if i == len(chunks) - 1 else 0
            self.unacked.append((self.next_seq, last, chunk))
            self.next_seq += 1
        self._send_unacked()

    def _send_unacked(self):
        self._since_send = 0
        for seq, last, chunk in self.unacked:
            self.t.send(TAG_CTRL, _CTRL_HDR.pack(seq, last, 0, len(chunk)) + chunk)

    def tick(self, datagrams):
        out = []
        for tag, _, payload in datagrams:
            if tag == TAG_CACK and len(payload) >= 4:
                acked = struct.unpack_from("<I", payload)[0]
                self.unacked = [(s, l, c) for s, l, c in self.unacked if s > acked]
            elif tag == TAG_CTRL and len(payload) >= _CTRL_HDR.size:
                seq, last, _, n = _CTRL_HDR.unpack_from(payload)
                chunk = payload[_CTRL_HDR.size:_CTRL_HDR.size + n]
                if seq > self.delivered:
                    self.early[seq] = (last, chunk)
                self._ack_due = True
        while self.delivered + 1 in self.early:
            self.delivered += 1
            last, chunk = self.early.pop(self.delivered)
            self._rx_buf.extend(chunk)
            if last:
                try:
                    out.append(zlib.decompress(bytes(self._rx_buf)))
                except zlib.error:
                    pass
                self._rx_buf.clear()
        if self._ack_due:
            self.t.send(TAG_CACK, struct.pack("<I", self.delivered))
            self._ack_due = False
        self._since_send += 1
        if self.unacked and self._since_send >= self.resend_every:
            self._send_unacked()
        return out
