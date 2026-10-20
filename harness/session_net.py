"""M7b: online play over simulated real-world networks (design/M7b-polish.md part 6,
design/M7b-netcode.md).

Each profile (link/netsim.py) runs the same session: A walks into the entrance hall (the
authority), B arrives next to it (the guest), then A paces back and forth while B fights, gold
is granted now and then, and finally the network drops out for 3 s. What a player feels is
measured on B's side:
- partner latency: how old the partner B sees is (ms), and how smoothly it moves (the share of
  frames whose step differs from the partner's real step: a stutter or a skip);
- enemies: the share of B's frames with a fresh snapshot, and the longest run without one;
- grants: how long a find takes to reach the partner;
- shared-room stability: role changes (each one is a hand-over the players can see);
- bandwidth each way, and the host's time per frame (it must never wait for the network);
- recovery: frames after the outage until the room is shared again.

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


def measure(run, profile, frames=1500, seed=1):
    s, a, b = run.s, run.s.a, run.s.b
    if profile:
        s.set_net(profile, seed)
    into_hall(run)
    run.step(60)
    for g in (a, b):
        g.host_ms()
    wa0, wb0 = a.transport("wan_stats"), b.transport("wan_stats")

    truth = {}                 # A's frame -> x
    lat, shown = [], []        # B: partner age (frames), (partner frame, x)
    snaps_b, snaps_a = [], []  # snapshot sequence numbers per frame
    roles = []
    grants, pending = [], []   # grant latencies (frames); (frame sent, B gold wanted)
    gold_b = status(b)["gold"]
    gold_a = status(a)["gold"]
    k = 0
    for i in range(frames):
        pad_a = "right" if (i // 90) % 2 == 0 else "left"
        pad_b = "square" if i % 20 == 0 else ""
        if i % 45 == 10:
            gold_a += 1
            k += 1
            a.write("g_Status", gold_a, "<i", GOLD)
            pending.append((i, gold_b + k))
        run.step(1, p1=(pad_a, pad_b))
        pa, pb = a.mailbox("self_presence"), b.mailbox("partner_presence")
        truth[pa.frame] = pa.x
        lat.append(pa.frame - pb.frame)
        shown.append((pb.frame, pb.x))
        snaps_a.append(a.mailbox("snapshot_out")[0] if i % 1 == 0 else 0)
        snaps_b.append(b.mailbox("snapshot_in_seq"))
        roles.append(b.mailbox("self_presence").role)
        if pending:
            gb = status(b)["gold"]
            while pending and gb >= pending[0][1]:
                grants.append(i - pending.pop(0)[0])
    secs = frames / 60
    wa1, wb1 = a.transport("wan_stats"), b.transport("wan_stats")
    host_ms = a.host_ms() + b.host_ms()

    # Smoothness: B's partner should step exactly as A did, one frame of A per frame of B.
    stutter = moved = 0
    for (f0, x0), (f1, x1) in zip(shown, shown[1:]):
        if f0 in truth and f1 - 1 in truth and f1 in truth:
            real = truth[f1] - truth[f1 - 1] if f1 - 1 in truth else 0
            if real:
                moved += 1
                stutter += (x1 - x0) != real
    fresh = sum(1 for p, q in zip(snaps_b, snaps_b[1:]) if q != p)
    made = sum(1 for p, q in zip(snaps_a, snaps_a[1:]) if q != p)
    gap = run_ = 0
    for p, q in zip(snaps_b, snaps_b[1:]):
        run_ = 0 if q != p else run_ + 1
        gap = max(gap, run_)
    changes = sum(1 for p, q in zip(roles, roles[1:]) if q != p)

    # The connection drops for 3 s, then comes back.
    recover, changes_out = None, 0
    if profile:
        for g in (a, b):
            g.transport("netsim_outage", 3.0)
        prev = b.mailbox("self_presence").role
        for i in range(180 + 900):
            run.step(1, p1=("", ""))
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
        "recover_ms": None if recover is None else round(recover * FRAME_MS),
        "outage_role_changes": changes_out,
        "sim_a": a.transport("netsim_stats"),
    }


COLUMNS = ("profile", "latency_ms", "latency_p95_ms", "stutter_pct", "snap_fresh_pct", "snap_gap_frames",
           "grant_ms", "grant_max_ms", "role_changes", "guest_pct", "up_kbps", "down_kbps", "pps",
           "host_ms_p99", "recover_ms", "outage_role_changes")


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
