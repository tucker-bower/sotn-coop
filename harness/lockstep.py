#!/usr/bin/env python3
"""Lockstep desync check: stands in for netplay.

    python lockstep.py [--minutes 10] [--start entrance] [--disc path.cue]

Instance A (one process) plays from a savestate with seeded random inputs on both pads and records
them. Instance B (a fresh process) replays A's inputs and, every `rollback_every` frames, saves and
reloads its own state, the way RetroArch netplay rolls back. Both hash all 8MB of RAM every second and
the full emulator state every 10 seconds. Any mismatch is a desync. Separate processes because
a libretro core can only be loaded once per process.
"""

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time

from coop_env import DISKS, TOOLS, savestate
from emu import Emu

HASH_EVERY, STATE_HASH_EVERY = 60, 600
DIRS = ["", "left", "right", "up", "down", "left+cross", "right+cross"]
ACTIONS = ["", "", "square", "circle", "cross", "triangle"]


def random_inputs(seed, frames):
    """Seeded button-mashing for both pads: holds a choice for 4-40 frames, like a twitchy player."""
    rng = random.Random(seed)
    pads, hold = [0, 0], [0, 0]
    for _ in range(frames):
        for p in (0, 1):
            if hold[p] == 0:
                pads[p] = "+".join(b for b in (rng.choice(DIRS), rng.choice(ACTIONS)) if b)
                hold[p] = rng.randint(4, 40)
            hold[p] -= 1
        yield tuple(pads)


def worker(role, disc, start, frames, seed, inputs_path, rollback_every, inject_desync=None):
    hashes, state_hashes = {}, {}
    with Emu(disc) as e:
        e.load_state_file(savestate(disc, start))
        if role == "A":
            inputs = list(random_inputs(seed, frames))
            inputs_path.write_text(json.dumps(inputs))
        else:
            inputs = json.loads(inputs_path.read_text())
        for i, (p1, p2) in enumerate(inputs, 1):
            e.step(1, p1, p2)
            if role == "B" and i == inject_desync:  # negative control: proves the check can fail
                e.write("g_Status", e.read("g_Status", "<i", 0x23C) - 1, "<i", 0x23C)
            if role == "B" and rollback_every and i % rollback_every == 0:
                e.load_state(e.save_state())
            if i % HASH_EVERY == 0:
                hashes[i] = e.ram_hash()
            if i % STATE_HASH_EVERY == 0:
                # Frame counter prefix excluded: it's harness bookkeeping, not emulator state.
                state_hashes[i] = hashlib.sha1(e.save_state()[8:]).hexdigest()
        final = e.snapshot()
    return {"hashes": hashes, "state_hashes": state_hashes, "final": final}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--start", default="entrance")
    ap.add_argument("--disc", default=str(DISKS / "sotn.us.cue"))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--rollback-every", type=int, default=600)
    ap.add_argument("--inject-desync", type=int, metavar="FRAME", help="B corrupts player HP at FRAME")
    ap.add_argument("--worker", choices=["A", "B"])
    args = ap.parse_args()
    out = TOOLS["out"] / "lockstep"
    out.mkdir(parents=True, exist_ok=True)
    frames = int(args.minutes * 60 * 60)

    if args.worker:
        r = worker(args.worker, args.disc, args.start, frames, args.seed, out / "inputs.json",
                   args.rollback_every, args.inject_desync)
        (out / f"{args.worker}.json").write_text(json.dumps(r))
        return

    t0 = time.time()
    base = [sys.executable, __file__, "--minutes", str(args.minutes), "--start", args.start,
            "--disc", args.disc, "--seed", str(args.seed), "--rollback-every", str(args.rollback_every)]
    if args.inject_desync:
        base += ["--inject-desync", str(args.inject_desync)]
    for role in ("A", "B"):  # B needs A's recorded inputs
        subprocess.run(base + ["--worker", role], check=True, capture_output=True)
    a, b = (json.loads((out / f"{r}.json").read_text()) for r in ("A", "B"))
    ram_diff = [f for f in a["hashes"] if a["hashes"][f] != b["hashes"].get(f)]
    state_diff = [f for f in a["state_hashes"] if a["state_hashes"][f] != b["state_hashes"].get(f)]
    report = {
        "passed": not ram_diff and not state_diff, "frames": frames, "minutes": args.minutes,
        "start": args.start, "seed": args.seed, "rollback_every": args.rollback_every,
        "ram_checks": len(a["hashes"]), "state_checks": len(a["state_hashes"]),
        "first_ram_desync_frame": int(ram_diff[0]) if ram_diff else None,
        "first_state_desync_frame": int(state_diff[0]) if state_diff else None,
        "final_A": a["final"], "final_B": b["final"], "seconds": round(time.time() - t0, 1),
    }
    (out / "report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
