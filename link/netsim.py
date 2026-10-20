"""A simulated internet between two hosts, for tests and for feeling a bad connection at home.

Each direction of the link gets its own model: a base one-way delay, jitter that comes and goes
the way queues do (correlated, right-skewed, with the odd spike), random or bursty loss
(Gilbert-Elliott), rare reordering and duplication, a bandwidth cap with a bounded queue, and
scheduled outages. Everything is seeded, and time comes from a clock the caller provides: in
the harness, the games' virtual time (frames / 60), so 75 ms means 4.5 frames however fast the
harness runs; in the launcher, the wall clock.

The model runs on the receiving side. The sender stamps each datagram with its clock (8 bytes,
sim mode only, never on a real network), and the receiver decides when, and whether, it
arrives. Both games' clocks are the same virtual timeline in the harness."""

import heapq
import random
import struct

STAMP = struct.Struct("<d")
UDP_IP_OVERHEAD = 28  # bytes per datagram on the wire, for the bandwidth cap

# One-way numbers (ms). jitter: the mean extra queueing delay; spike: chance per packet of a
# Wi-Fi-style stall of spike_ms on top; burst: mean length of a loss burst, in packets.
PROFILES = {
    "lan":           dict(delay=1,  jitter=0.3, loss=0.0),
    "city":          dict(delay=10, jitter=3,   loss=0.001),
    "country":       dict(delay=30, jitter=6,   loss=0.005),
    "transatlantic": dict(delay=55, jitter=10,  loss=0.01, burst=1.5),
    "wifi":          dict(delay=15, jitter=20,  loss=0.03, burst=4, spike=0.004, spike_ms=150),
    "cellular":      dict(delay=45, jitter=25,  loss=0.02, burst=2, spike=0.002, spike_ms=250, kbps=1500),
}
PROFILE_WORDS = {  # what each profile stands for, round trip
    "lan": "same house (2 ms)",
    "city": "same city (20 ms)",
    "country": "across the country (60 ms)",
    "transatlantic": "across an ocean (110 ms, 1% loss)",
    "wifi": "bad Wi-Fi (30–300 ms, 3% loss in bursts)",
    "cellular": "phone hotspot (90–500 ms, 2% loss, 1.5 Mbit/s)",
}


class Direction:
    """One direction of the link: when (and whether) each datagram arrives."""

    def __init__(self, delay=0, jitter=0, loss=0.0, burst=1.0, spike=0.0, spike_ms=0, kbps=0,
                 queue_ms=250, reorder=0.002, duplicate=0.0005, seed=1):
        self.delay, self.jitter = delay / 1000, jitter / 1000
        self.spike, self.spike_s = spike, spike_ms / 1000
        self.kbps, self.queue_s = kbps, queue_ms / 1000
        self.reorder, self.duplicate = reorder, duplicate
        self.rng = random.Random(seed)
        # Gilbert-Elliott: in the bad state everything is lost. Mean burst length `burst`
        # packets, overall loss `loss`.
        self.p_bg = 1 / max(1.0, burst)
        self.p_gb = loss * self.p_bg / (1 - loss) if 0 < loss < 1 else (1.0 if loss >= 1 else 0.0)
        self.bad = False
        self.q = 0.0            # the correlated jitter's current level (s)
        self.link_free = 0.0    # bandwidth cap: when the link is next idle
        self.last_arrival = 0.0
        self.stall_until = 0.0  # a spike delays everything behind it, in order
        self.outages = []       # [(start, end)] times when everything is lost
        self.stats = dict(sent=0, lost=0, queue_drops=0, outage=0, reordered=0, duplicated=0)

    def fate(self, sent_at, size):
        """Arrival times for a datagram sent at sent_at: [] if it's lost, two if duplicated."""
        st = self.stats
        st["sent"] += 1
        if any(a <= sent_at < b for a, b in self.outages):
            st["outage"] += 1
            return []
        self.bad = (self.rng.random() >= self.p_bg) if self.bad else (self.rng.random() < self.p_gb)
        if self.bad:
            st["lost"] += 1
            return []
        depart = sent_at
        if self.kbps:
            depart = max(sent_at, self.link_free)
            if depart - sent_at > self.queue_s:  # the router's queue is full: tail drop
                st["queue_drops"] += 1
                return []
            self.link_free = depart + (size + UDP_IP_OVERHEAD) * 8 / (self.kbps * 1000)
        # Jitter, mean `jitter`: a slow part (queues filling and draining: an AR(1) walk) and a
        # fast part (per packet), both gamma-distributed (right-skewed, never below zero).
        extra = 0.0
        if self.jitter:
            self.q = 0.9 * self.q + 0.1 * self.rng.gammavariate(2.0, 0.6 * self.jitter / 2)
            extra = self.q + self.rng.gammavariate(1.5, 0.4 * self.jitter / 1.5)
        arrive = depart + self.delay + extra
        if self.spike and self.rng.random() < self.spike:
            self.stall_until = max(self.stall_until, arrive + self.spike_s * self.rng.uniform(0.5, 1.5))
        arrive = max(arrive, self.stall_until)
        if self.rng.random() < self.reorder:
            arrive += self.rng.uniform(0.005, 0.03)  # this one alone takes a detour
            st["reordered"] += 1
        else:
            arrive = max(arrive, self.last_arrival)  # otherwise the network keeps order
            self.last_arrival = arrive
        out = [arrive]
        if self.rng.random() < self.duplicate:
            out.append(arrive + self.rng.uniform(0, 0.01))
            st["duplicated"] += 1
        return out


class NetSim:
    """The receiving end of a simulated link. Datagrams come in stamped with their send time;
    ready() hands back the ones that have arrived by now."""

    def __init__(self, clock, profile="lan", seed=1, **overrides):
        params = dict(PROFILES[profile]) if isinstance(profile, str) else dict(profile or {})
        params.update(overrides)
        self.profile = profile if isinstance(profile, str) else "custom"
        self.clock = clock
        self.dir = Direction(seed=seed, **params)
        self._heap = []
        self._n = 0

    def stamp(self, data):
        return STAMP.pack(self.clock()) + data

    def arrive(self, data, addr):
        """A stamped datagram from the socket: schedule its arrival (or lose it)."""
        if len(data) < STAMP.size:
            return
        sent_at = STAMP.unpack_from(data)[0]
        body = data[STAMP.size:]
        for t in self.dir.fate(sent_at, len(body)):
            self._n += 1
            heapq.heappush(self._heap, (t, self._n, body, addr))

    def ready(self):
        now = self.clock()
        out = []
        while self._heap and self._heap[0][0] <= now:
            _, _, body, addr = heapq.heappop(self._heap)
            out.append((body, addr))
        return out

    def outage(self, start, seconds):
        self.dir.outages.append((start, start + seconds))

    def stats(self):
        return dict(self.dir.stats, profile=self.profile, in_flight=len(self._heap))
