"""M7b: online play over simulated real-world networks (design/M7b-polish.md part 6,
design/M7b-netcode.md).

Each profile (link/netsim.py) runs the same session: A walks into the entrance hall (the
authority), B arrives next to it (the guest), then A paces back and forth while B fights, gold
is granted now and then, and finally the network drops out for 3 s. What a player feels is
measured on B's side:
- partner latency: how old the partner B sees is (ms), and how smoothly it moves (stutter: the
  share of frames with a hitch, a stall-then-jump, that the partner's real movement didn't have);
- enemies: the share of B's frames with a fresh snapshot, and the longest run without one;
- grants: how long a find takes to reach the partner;
- shared-room stability: role changes (each one is a hand-over the players can see);
- bandwidth each way, and the host's time per frame (it must never wait for the network);
- reaction: B's round trip plus the playout delay, about how long an enemy B hits takes to react;
- recovery: a 0.4 s blip must not hand the room over; after a 3 s outage, how long until the room
  is shared again.
Along the way A's PC hitches once (167 ms), and A's clock runs 0.1% fast.

    python harness/session_net.py [profile ...]    prints the table
"""

import json
import statistics
import sys

from session import Session, SessionRun, session_scenario  # first: puts `link` on the path

from coop_env import TOOLS
from link.mailbox import ROLE_GUEST
from link.netsim import PROFILES
from session_progress import status
from session_shared import into_hall

GOLD = 0x28C
FRAME_MS = 1000 / 60


def _q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p))] if v else None


class Timed:
    """Steps the two games on one virtual timeline, as two PCs would run them: whichever game's
    next frame is due first runs. A's PC runs a little fast (two PCs never quite agree on
    60 Hz), and a stalled PC misses frames while the other one keeps going."""

    def __init__(self, s, drift):
        self.s = s
        self.dt = [1 / (60 * (1 + drift)), 1 / 60]
        self.t = [0.0, 1 / 120]
        self.stalled = [0, 0]
        s.a.set_rate(1 / self.dt[0])

    def frame(self, pads):
        """Runs until B has run one frame (A runs as many as are due by then)."""
        while True:
            i = 0 if self.t[0] <= self.t[1] else 1
            g = self.s.games[i]
            if self.stalled[i]:
                self.stalled[i] -= 1
                g.stall(1)
            else:
                g.step(1, pads[i])
            self.t[i] += self.dt[i]
            if i == 1:
                return

    def stall(self, i, frames):
        self.stalled[i] += frames


def measure(run, profile, frames=1500, seed=1, drift=0.001):
    s, a, b = run.s, run.s.a, run.s.b
    if profile:
        s.set_net(profile, seed)
    into_hall(run)
    run.step(60)
    timed = Timed(s, drift if profile else 0.0)
    for g in (a, b):
        g.host_ms()
    wa0, wb0 = a.transport("wan_stats"), b.transport("wan_stats")

    truth = {}                 # A's frame -> x
    lat, shown = [], []        # B: partner age (frames), (partner frame, x)
    snaps_b, snaps_a = [], []  # snapshot sequence numbers per frame
    roles = []
    grants, pending = [], []   # grant latencies (frames); (frame sent, B gold wanted)
    reaction = []              # B: RTT + playout delay: from B's hit to the enemy's reaction
    gold_b = status(b)["gold"]
    gold_a = status(a)["gold"]
    k = 0
    for i in range(frames):
        pad_a = "right" if (i // 90) % 2 == 0 else "left"
        pad_b = "square" if i % 20 == 0 else ""
        if i == 700:
            timed.stall(0, 10)  # A's PC hitches for 167 ms
        if i % 45 == 10:
            gold_a += 1
            k += 1
            a.write("g_Status", gold_a, "<i", GOLD)
            pending.append((i, gold_b + k))
        timed.frame((pad_a, pad_b))
        pa, pb = a.mailbox("self_presence"), b.mailbox("partner_presence")
        truth[pa.frame] = pa.x
        lat.append(pa.frame - pb.frame)
        shown.append((pb.frame, pb.x))
        snaps_a.append(a.mailbox("snapshot_out")[0] if i % 1 == 0 else 0)
        snaps_b.append(b.mailbox("snapshot_in_seq"))
        roles.append(b.mailbox("self_presence").role)
        if i % 30 == 0:
            q = b.host("status")
            if q["rtt_ms"] is not None:
                reaction.append(q["rtt_ms"] + (q["playout"] or {}).get("delay_ms", 0))
        if pending:
            gb = status(b)["gold"]
            while pending and gb >= pending[0][1]:
                grants.append(i - pending.pop(0)[0])
    secs = frames / 60
    wa1, wb1 = a.transport("wan_stats"), b.transport("wan_stats")
    host_ms = a.host_ms() + b.host_ms()

    # Smoothness: a hitch is a sudden change in the partner's step from one frame to the next
    # (a stall, then a jump). Real movement has some too (turning around): the stutter is the
    # hitches B sees beyond the ones A really made.
    def hitches(xs):
        d = [b - a for a, b in zip(xs, xs[1:])]
        return sum(1 for p, q in zip(d, d[1:]) if abs(q - p) >= 2)
    real = [truth[f] for f in sorted(truth)]
    seen = [x for _, x in shown]
    stutter, moved = max(0, hitches(seen) - hitches(real)), len(seen)
    fresh = sum(1 for p, q in zip(snaps_b, snaps_b[1:]) if q != p)
    made = sum(1 for p, q in zip(snaps_a, snaps_a[1:]) if q != p)
    gap = run_ = 0
    for p, q in zip(snaps_b, snaps_b[1:]):
        run_ = 0 if q != p else run_ + 1
        gap = max(gap, run_)
    changes = sum(1 for p, q in zip(roles, roles[1:]) if q != p)

    # A short blip (0.4 s) must not hand the room over; then the connection drops for 3 s.
    recover, changes_out, changes_blip = None, 0, 0
    if profile:
        for g in (a, b):
            g.transport("netsim_outage", 0.4)
        prev = b.mailbox("self_presence").role
        for i in range(120):
            timed.frame(("", ""))
            r = b.mailbox("self_presence").role
            changes_blip += r != prev
            prev = r
        for g in (a, b):
            g.transport("netsim_outage", 3.0)
        prev = b.mailbox("self_presence").role
        for i in range(180 + 900):
            timed.frame(("", ""))
            r = b.mailbox("self_presence").role
            changes_out += r != prev
            prev = r
            if i >= 180 and r == ROLE_GUEST and b.mailbox("partner_age") == 0:
                recover = i - 180
                break
    return {
        "profile": profile or "none",
        "latency_ms": round(statistics.median(lat) * FRAME_MS),
        "latency_p95_ms": round(_q(lat, 0.95) * FRAME_MS),
        "stutter_pct": round(100 * stutter / max(1, moved), 1),
        "snap_fresh_pct": round(100 * fresh / max(1, made), 1),
        "snap_gap_frames": gap,
        "grant_ms": round(statistics.median(grants) * FRAME_MS) if grants else None,
        "grant_max_ms": round(max(grants) * FRAME_MS) if grants else None,
        "grants": f"{len(grants)}/{k}",
        "role_changes": changes,
        "guest_pct": round(100 * sum(r == ROLE_GUEST for r in roles) / len(roles), 1),
        "up_kbps": round((wa1["bytes_sent"] - wa0["bytes_sent"]) * 8 / secs / 1000),
        "down_kbps": round((wb1["bytes_sent"] - wb0["bytes_sent"]) * 8 / secs / 1000),
        "pps": round((wa1["packets_sent"] - wa0["packets_sent"]) / secs),
        "host_ms_p99": round(_q(host_ms, 0.99), 2) if host_ms else None,
        "reaction_ms": round(statistics.median(reaction)) if reaction else None,
        "blip_role_changes": changes_blip,
        "recover_ms": None if recover is None else round(recover * FRAME_MS),
        "outage_role_changes": changes_out,
        "sim_a": a.transport("netsim_stats"),
    }


COLUMNS = ("profile", "latency_ms", "latency_p95_ms", "stutter_pct", "snap_fresh_pct", "snap_gap_frames",
           "grant_ms", "grant_max_ms", "role_changes", "guest_pct", "up_kbps", "down_kbps", "pps",
           "host_ms_p99", "reaction_ms", "blip_role_changes", "recover_ms", "outage_role_changes")


def table(rows):
    lines = ["| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in COLUMNS) + " |")
    return "\n".join(lines)


def run_profiles(profiles):
    from module import COOP_DISC
    rows = []
    for p in profiles:
        with Session(COOP_DISC) as s:
            run = SessionRun(s, "net_" + (p or "none"), gif_every=10**9)
            run.capture = lambda: None
            rows.append(measure(run, p))
            print(table(rows[-1:]).splitlines()[-1], flush=True)
    out = TOOLS["out"] / "net_profiles"
    out.mkdir(parents=True, exist_ok=True)
    (out / "table.md").write_text(table(rows) + "\n")
    (out / "rows.json").write_text(json.dumps(rows, indent=1))
    return rows


if __name__ == "__main__":
    names = sys.argv[1:] or [None, *PROFILES]
    print(table([]))
    run_profiles([None if n == "none" else n for n in names])
