"""Messages between the two hosts: UDP datagrams, on localhost or across the internet.

Wire protocol version 9 (docs/link-protocol.md). Every datagram carries the sender's frame, so
the receiver can play the partner's state back at an even pace (link/playout.py).
Presence is state, not a stream of events, so a lost or late datagram only costs freshness. It
also carries the snapshot ack and the timestamps the round-trip time is measured with, so no
extra datagrams are needed for either.
Progression events must arrive exactly once and in order: ReliableChannel adds sequence
numbers, cumulative acks and resends (on a timeout from the measured round-trip time).
Shared-room snapshots are delta-compressed against a snapshot the receiver has acked (XOR with
it, then zlib: a few hundred bytes instead of ~1.6 KB), and split into chunks
of at most 1200 bytes per UDP packet so routers never fragment them (D74)."""

import random
import socket
import struct
import time
import zlib
import collections
from collections import OrderedDict

WIRE_VERSION = 9
_HEADER = struct.Struct("<4sII")  # tag, sequence number, the sender's frame
TAG_PRESENCE = b"PRES"  # payload: presence (0x2C), then _PRES_TAIL
TAG_EVENTS = b"EVTS"    # payload: first seq (u32), then events
TAG_ACK = b"ACK "       # payload: highest seq delivered in order (u32)
TAG_SNAP = b"SNAP"      # (receive() only) a reassembled shared-room snapshot
TAG_SNPC = b"SNPC"      # payload: snap_id (u32), base_id (u32), chunk_idx (u8), chunk_cnt (u8), zlib chunk
TAG_CTRL = b"CTRL"      # payload: seq (u32), last (u8), pad (u8), len (u16), chunk (reliable control/save)
TAG_CACK = b"CACK"      # payload: highest CTRL seq delivered in order (u32)
TAG_SPRT = b"SPRT"      # payload: the sender's sprites (CoopSprite records, sprites.c): its attacks, drawn by the partner
TAG_BYE = b"BYE "       # payload: the sender's HELO sid (JSON): it is leaving (the app closed, or back to its menu)
TAG_HELLO = b"HELO"     # payload: JSON {"link": WIRE_VERSION, "patch": target CRC32 or null}, once a second

PRESENCE_SIZE = 0x2C
# After the presence: the newest snapshot id decoded (u32), the sender's clock (ms, u32), the
# newest clock heard from the partner (ms, u32), and how long ago that was heard (ms, u16).
_PRES_TAIL = struct.Struct("<IIIHxx")
_SNPC_HDR = struct.Struct("<IIBB")
_CTRL_HDR = struct.Struct("<IBBH")
MAX_SNAP_CHUNK = 1150  # keeps total UDP payload <= 1176 bytes (well below a 1200-byte path MTU)
MAX_CTRL_CHUNK = 1000
SNAP_HISTORY = 64      # snapshots kept as delta bases, both ends (about a second)
FRAME_S = 1 / 60


def _xor(data, base):
    """data XOR base (base cut or zero-padded to data's length). Unchanged bytes become zeros,
    which compress to almost nothing: a snapshot differs from a recent one in a few bytes per
    entity (positions, timers), scattered (design/M7b-netcode.md)."""
    n = len(data)
    b = base[:n].ljust(n, b"\0")
    return (int.from_bytes(data, "little") ^ int.from_bytes(b, "little")).to_bytes(n, "little")


class RttEstimator:
    """Round-trip time, as TCP measures it (RFC 6298): smoothed, with its variation."""

    def __init__(self):
        self.srtt = None
        self.rttvar = 0.0
        self.last = None
        self.samples = 0

    def sample(self, rtt):
        self.last = rtt
        self.samples += 1
        if self.srtt is None:
            self.srtt, self.rttvar = rtt, rtt / 2
        else:
            self.rttvar = 0.75 * self.rttvar + 0.25 * abs(self.srtt - rtt)
            self.srtt = 0.875 * self.srtt + 0.125 * rtt

    def rto(self):
        """How long to wait for an ack before resending: one round trip, its variation, and the
        frame each end may take to answer."""
        if self.srtt is None:
            return 0.25
        return min(1.0, max(0.05, self.srtt + max(4 * self.rttvar, FRAME_S) + 2 * FRAME_S))


class UdpTransport:
    """port 0 binds any free port (see .port); a tuple of ports tries each in turn (the game's
    usual port, then any: link/connect.py GAME_PORT). The peer can be set later with connect()."""

    def __init__(self, port=0, peer_port=None, host="127.0.0.1", bind_host=None, sock=None):
        """sock: a socket to use instead of a new UDP one (link/natsim.py's virtual ones)."""
        self.host = host
        self.peer = None
        self.peer_confirmed = False  # a valid HELO came from self.peer (link/host.py)
        if peer_port is not None:
            self.connect(peer_port)
        self.sock = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ports = tuple(port) if isinstance(port, (tuple, list)) else (port,)
        for i, p in enumerate(ports):
            try:
                self.sock.bind((bind_host or host, p))
                break
            except OSError:  # taken (another game on this PC): the next one
                if i == len(ports) - 1:
                    raise
        self.sock.setblocking(False)
        self.port = self.sock.getsockname()[1]
        self.seq = 0
        self.frame = 0            # the host's frame, stamped on everything sent
        self.partitioned = False  # tests: drop everything both ways, like a dead network
        self.learn_peer = False   # online: the peer is whoever sends a valid HELO (accept_peer);
        #                           everything else from other addresses is ignored
        self.stun_results = {}    # STUN server -> our address as it saw it
        self._stun_tx = {}
        self.last_rx_time = None
        # Time, for everything that waits: the wall clock, or the harness's virtual time
        self.clock = time.monotonic
        self.sim = None           # a simulated internet on the way in (link/netsim.py)
        self.rtt = RttEstimator()
        self._heard_ms = 0        # the partner's clock in its newest presence, and when
        self._heard_at = None
        # Snapshots, sending: what we sent (delta bases) and the newest the partner decoded
        self._snap_id = 0
        self._sent_snaps = OrderedDict()
        self._snap_acked = 0
        self.snap_stats = collections.deque(maxlen=600)  # (frames back to the base or 0, raw, compressed)
        # Snapshots, receiving: chunks being put together, and decoded snapshots (delta bases)
        self._snap_parts = {}     # snap_id -> {"cnt": chunks, "parts": {chunk_idx: bytes}}
        self._snap_done = 0       # newest snap_id decoded
        self._got_snaps = OrderedDict()
        self.snap_undecodable = 0
        # Loss, as the share of the partner's presences (one per frame) that never arrived
        self._pres_frames = []
        self.max_packet_sent = 0
        self.bytes_sent = self.packets_sent = 0  # on the wire, with UDP/IP headers
        self.bytes_received = 0
        # Simple sender-side limits for harness tests (set_wan)
        self.mtu = 0              # if > 0, drop any UDP payload > self.mtu bytes
        self.mtu_drops = 0
        self.loss = 0.0           # fraction of packets randomly dropped (0.0 - 1.0)
        self.loss_drops = 0
        self._rng = random.Random(1)

    def accept_peer(self, addr):
        """A valid HELO came from addr: that's the partner (or the partner's new address, when
        its router changed the mapping)."""
        self.peer = (str(addr[0]), int(addr[1]))
        self.peer_confirmed = True

    def probe(self, addr, tag, payload):
        """One datagram to an address that isn't (yet) the peer: hole punching."""
        peer, self.peer = self.peer, (str(addr[0]), int(addr[1]))
        try:
            self._send_datagram(tag, payload)
        finally:
            self.peer = peer

    def stun_request(self, server):
        """Asks a STUN server (ip, port) for our public address, from this very socket."""
        import os
        from .rendezvous import MAGIC_COOKIE
        tx = os.urandom(12)
        self._stun_tx[tx] = tuple(server)
        try:
            self.sock.sendto(struct.pack(">HHI12s", 0x0001, 0, MAGIC_COOKIE, tx), tuple(server))
        except OSError:
            pass

    def _stun_reply(self, data):
        from .rendezvous import _parse_stun_response
        tx = data[8:20]
        server = self._stun_tx.get(tx)
        if server:
            mapped = _parse_stun_response(data, tx)
            if mapped:
                self.stun_results[server] = mapped

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

    def set_wan(self, mtu=0, loss=0.0, seed=1):
        """Simple sender-side limits for harness tests: an MTU cap and random loss."""
        self.mtu = int(mtu)
        self.loss = float(loss)
        self._rng = random.Random(seed)
        return True

    def set_netsim(self, profile="lan", seed=1, **overrides):
        """A simulated internet (link/netsim.py) on datagrams coming in. Both ends must turn it
        on (it adds a timestamp to every datagram). profile=None turns it off."""
        from .netsim import NetSim
        self.sim = NetSim(self.clock, profile, seed, **overrides) if profile else None
        return True

    def netsim_outage(self, seconds, start=None):
        """Simulated: nothing gets through, starting now (or at `start`), for `seconds`."""
        self.sim.outage(self.clock() if start is None else start, seconds)
        return True

    def netsim_stats(self):
        return self.sim.stats() if self.sim else None

    def wan_stats(self):
        return {
            "max_packet_sent": self.max_packet_sent,
            "mtu_drops": self.mtu_drops,
            "loss_drops": self.loss_drops,
            "bytes_sent": self.bytes_sent,
            "packets_sent": self.packets_sent,
            "bytes_received": self.bytes_received,
            "snap_undecodable": self.snap_undecodable,
        }

    def snapshot_stats(self):
        """The last snapshots sent: (frames back to the delta base, or 0 for none; raw; sent)."""
        return list(self.snap_stats)

    def quality(self):
        """The connection as the player feels it: round trip (ms) and loss (%)."""
        f = self._pres_frames
        loss = None
        if len(f) >= 30:
            span = f[-1] - f[0] + 1
            loss = round(100 * max(0, span - len(f)) / span, 1)
        return {"rtt_ms": None if self.rtt.srtt is None else round(self.rtt.srtt * 1000),
                "rtt_var_ms": round(self.rtt.rttvar * 1000), "loss_pct": loss}

    def _ms(self):
        return int(self.clock() * 1000) & 0xFFFFFFFF

    def _send_datagram(self, tag, payload):
        if self.peer is None or self.partitioned:
            return
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        pkt = _HEADER.pack(tag, self.seq, self.frame & 0xFFFFFFFF) + payload
        if len(pkt) > self.max_packet_sent:
            self.max_packet_sent = len(pkt)
        if self.mtu and len(pkt) > self.mtu:
            self.mtu_drops += 1
            return
        if self.loss > 0.0 and self._rng.random() < self.loss:
            self.loss_drops += 1
            return
        self.bytes_sent += len(pkt) + 28
        self.packets_sent += 1
        if self.sim:
            pkt = self.sim.stamp(pkt)
        try:
            self.sock.sendto(pkt, self.peer)
        except OSError:  # partner not listening (yet, or any more): presence is best-effort
            pass

    def send(self, tag, payload):
        if self.peer is None or self.partitioned:
            return
        if tag == TAG_SNAP:
            self._send_snapshot(payload)
        elif tag == TAG_PRESENCE:
            tail = _PRES_TAIL.pack(self._snap_done, *self.clock_stamp())
            self._send_datagram(tag, payload[:PRESENCE_SIZE] + tail)
        else:
            self._send_datagram(tag, payload)

    def _send_snapshot(self, raw):
        self._snap_id = (self._snap_id + 1) & 0xFFFFFFFF
        base = self._snap_acked if self._snap_acked in self._sent_snaps else 0
        comp = zlib.compress(_xor(raw, self._sent_snaps[base]) if base else raw, 6)
        self.snap_stats.append((self._snap_id - base if base else 0, len(raw), len(comp)))
        self._sent_snaps[self._snap_id] = raw
        while len(self._sent_snaps) > SNAP_HISTORY:
            self._sent_snaps.popitem(last=False)
        chunks = [comp[i:i + MAX_SNAP_CHUNK] for i in range(0, max(1, len(comp)), MAX_SNAP_CHUNK)]
        for idx, chunk in enumerate(chunks):
            self._send_datagram(TAG_SNPC, _SNPC_HDR.pack(self._snap_id, base, idx, len(chunks)) + chunk)

    def receive(self):
        """All datagrams waiting right now, as (tag, seq, frame, payload, from), oldest first.
        Snapshot chunks come out as one TAG_SNAP once complete and decoded."""
        out = []
        for data, addr in self._datagrams():
            if self._stun_tx and len(data) >= 20 and data[:2] == b"\x01\x01":  # a STUN answer
                self._stun_reply(data)
                continue
            if len(data) < _HEADER.size or self.partitioned:
                continue
            tag, seq, frame = _HEADER.unpack_from(data)
            body = data[_HEADER.size:]
            addr = (str(addr[0]), int(addr[1]))
            if self.learn_peer and addr != self.peer and tag != TAG_HELLO:
                continue  # not from the partner: only a HELO can become the partner
            self.bytes_received += len(data) + 28
            self.last_rx_time = self.clock()
            if tag == TAG_SNPC:
                snap = self._snapshot_chunk(frame, body)
                if snap is not None:
                    out.append((TAG_SNAP, seq, snap[0], snap[1], addr))
            elif tag == TAG_PRESENCE:
                if len(body) >= PRESENCE_SIZE + _PRES_TAIL.size:
                    self._presence_tail(frame, body[PRESENCE_SIZE:PRESENCE_SIZE + _PRES_TAIL.size])
                out.append((tag, seq, frame, body[:PRESENCE_SIZE], addr))
            else:
                out.append((tag, seq, frame, body, addr))
        return out

    def clock_stamp(self):
        """(our clock, the partner's newest clock we heard, how long ago): in ms, for the
        round-trip measurement (presence tail, and HELO before the games run)."""
        hold = 0
        if self._heard_at is not None:
            hold = min(0xFFFF, int((self.clock() - self._heard_at) * 1000))
        return self._ms(), self._heard_ms, hold

    def clock_heard(self, their_ms, echo_ms, hold_ms):
        if their_ms >= self._heard_ms or self._heard_ms - their_ms > 0x80000000:  # newest (wraps)
            self._heard_ms, self._heard_at = their_ms, self.clock()
        if echo_ms:
            rtt = ((self._ms() - echo_ms) & 0xFFFFFFFF) - hold_ms
            if 0 <= rtt < 5000:
                self.rtt.sample(rtt / 1000)

    def _presence_tail(self, frame, tail):
        acked, their_ms, echo_ms, hold_ms = _PRES_TAIL.unpack(tail)
        if acked in self._sent_snaps and acked > self._snap_acked:
            self._snap_acked = acked
        self.clock_heard(their_ms, echo_ms, hold_ms)
        f = self._pres_frames
        if not f or frame > f[-1]:
            f.append(frame)
            if len(f) > 300:
                del f[:len(f) - 300]

    def _snapshot_chunk(self, frame, body):
        """A snapshot chunk: (frame, snapshot) once its snapshot is complete, else None."""
        if len(body) < _SNPC_HDR.size:
            return None
        snap_id, base, idx, cnt = _SNPC_HDR.unpack_from(body)
        if snap_id <= self._snap_done or cnt == 0 or idx >= cnt:
            return None
        bucket = self._snap_parts.setdefault(snap_id, {"cnt": cnt, "parts": {}})
        bucket["parts"][idx] = body[_SNPC_HDR.size:]
        if len(bucket["parts"]) < bucket["cnt"]:
            if len(self._snap_parts) > 8:
                del self._snap_parts[min(self._snap_parts)]
            return None
        comp = b"".join(bucket["parts"][i] for i in range(bucket["cnt"]))
        for old in [k for k in self._snap_parts if k <= snap_id]:
            del self._snap_parts[old]
        try:
            if base:
                if base not in self._got_snaps:  # we never decoded its base: wait for another
                    self.snap_undecodable += 1
                    return None
                raw = _xor(zlib.decompress(comp), self._got_snaps[base])
            else:
                raw = zlib.decompress(comp)
        except zlib.error:
            self.snap_undecodable += 1
            return None
        self._snap_done = snap_id
        self._got_snaps[snap_id] = raw
        while len(self._got_snaps) > SNAP_HISTORY:
            self._got_snaps.popitem(last=False)
        return frame, raw

    def _datagrams(self):
        """What came in from the socket, through the simulated internet if there is one."""
        raw = []
        while True:
            try:
                raw.append(self.sock.recvfrom(65536))
            except (BlockingIOError, ConnectionRefusedError, OSError):
                break
        if not self.sim:
            return raw
        for data, addr in raw:
            self.sim.arrive(data, addr)
        return self.sim.ready()

    def close(self):
        self.sock.close()


class ReliableChannel:
    """Exactly-once, in-order delivery of fixed-size records over a UdpTransport.

    The sender keeps every record until the peer acks it, and resends the unacked tail when no
    ack has come for a retransmission timeout (from the measured round trip); the receiver
    delivers in sequence order and drops duplicates. Call tick() once per frame with the
    datagrams of interest."""

    MAX_PER_DATAGRAM = 128

    def __init__(self, transport, record_size):
        self.t, self.size = transport, record_size
        self.next_seq = 1           # seq of the next record we queue
        self.unacked = []           # [(seq, record)]
        self.delivered = 0          # highest seq delivered to us in order
        self.early = {}             # seq -> record, received ahead of a gap
        self._sent_at = 0.0
        self._ack_due = False
        self.resends = 0

    def queue(self, records):
        for r in records:
            self.unacked.append((self.next_seq, r))
            self.next_seq += 1
        if records:
            self._send_unacked()

    def _send_unacked(self):
        self._sent_at = self.t.clock()
        for i in range(0, len(self.unacked), self.MAX_PER_DATAGRAM):
            chunk = self.unacked[i:i + self.MAX_PER_DATAGRAM]
            self.t.send(TAG_EVENTS, struct.pack("<I", chunk[0][0]) + b"".join(r for _, r in chunk))

    def tick(self, datagrams):
        """Handles this frame's EVTS/ACK datagrams; returns newly delivered records, in order."""
        out = []
        for tag, _, _, payload, _ in datagrams:
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
        if self.unacked and self.t.clock() - self._sent_at >= self.t.rtt.rto():
            self.resends += 1
            self._send_unacked()
        return out


class ReliableMessages:
    """Reliable, ordered delivery of arbitrary byte blobs (e.g. online joint saves) over UdpTransport.
    Blobs are zlib-compressed and split into <= MAX_CTRL_CHUNK pieces so every packet stays MTU-safe."""

    def __init__(self, transport):
        self.t = transport
        self.next_seq = 1
        self.unacked = []     # [(seq, last, chunk)]
        self.delivered = 0
        self.early = {}       # seq -> (last, chunk)
        self._rx_buf = bytearray()
        self._sent_at = 0.0
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
        self._sent_at = self.t.clock()
        for seq, last, chunk in self.unacked:
            self.t.send(TAG_CTRL, _CTRL_HDR.pack(seq, last, 0, len(chunk)) + chunk)

    def tick(self, datagrams):
        out = []
        for tag, _, _, payload, _ in datagrams:
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
        if self.unacked and self.t.clock() - self._sent_at >= self.t.rtt.rto():
            self._send_unacked()
        return out
