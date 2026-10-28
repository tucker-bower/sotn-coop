#!/usr/bin/env python3
"""Runs harness scenarios.

    python run.py [-j N] [--full] [scenario ...]

No names: the everyday suite, everything but the long ones (*_NNmin soaks, *_long), which --full
adds (before a playtest build) or run by name. Tests run side by side, each in its own process
(-j: how many at once; default the cores less 4: 12 on a 16-core PC, measured about 8 minutes;
-j 1 runs them one after another in this process). The tests that time the host in real time
(SOLO) run alone at the end. Each test's output goes to
.env/out/<name>/log.txt. Exit code 0 = all passed."""

import json
import os
import subprocess
import sys
import threading
import time

import scenarios  # noqa: F401  (registers scenarios)
import scenarios_m8  # noqa: F401
import session_scenarios  # noqa: F401
import session_progress  # noqa: F401
import session_travel  # noqa: F401
import session_saverooms  # noqa: F401
import session_shared  # noqa: F401
import session_m4b  # noqa: F401
import session_m5  # noqa: F401
import session_m8  # noqa: F401
import session_online  # noqa: F401
import session_m9  # noqa: F401
import session_m11  # noqa: F401
import session_m12  # noqa: F401
import scenarios_m12  # noqa: F401
import scenarios_relics  # noqa: F401
import spec_test  # noqa: F401
from scenario import SCENARIOS, run_scenario
from session import SESSION_SCENARIOS, run_session_scenario

LONG = ("min", "_long")  # name endings left out of the everyday suite
# Tests that use real sockets, a room-code relay or LAN broadcasts (fixed port 47811): one at a
# time, in their own lane, so two of them never hear each other.
NETWORK_MODULES = {"session_online", "session_m9", "session_m11", "spec_test"}
# Tests that time the host in real time (its p99 per frame): alone, after the rest, as other
# tests' load would be in their numbers.
SOLO = {"mixed_soak_short", "mixed_soak_10min", "mixed_soak_baseline_10min"}
# Tests that read another's output: (first, then) run in that order, in one lane.
CHAINS = []
TEST_TIMEOUT = 1800  # seconds: a test that hangs fails instead of holding up the run


def module_of(name):
    fn = SESSION_SCENARIOS[name][0] if name in SESSION_SCENARIOS else SCENARIOS[name][0]
    return fn.__module__


def run_one(name):
    return run_session_scenario(name) if name in SESSION_SCENARIOS else run_scenario(name)


def show(r, name):
    rooms = " -> ".join(f"{x['room'][0]},{x['room'][1]}" for x in r.get("rooms", []))
    detail = f"{r['frames']} frames in {r['seconds']}s; rooms {rooms}" if "frames" in r else f"{r['seconds']}s, two games"
    lines = [f"{'PASS' if r['passed'] else 'FAIL'} {name}: {detail}"]
    for c in r["checks"]:
        lines.append(f"   {'ok ' if c['ok'] else 'BAD'} {c['what']}")
    if r["error"]:
        lines.append("   " + r["error"].strip().replace("\n", "\n   "))
    return "\n".join(lines)


def last_seconds(name):
    """How long the test took last time (longest first packs the run best)."""
    from coop_env import TOOLS
    try:
        return json.loads((TOOLS["out"] / name / "report.json").read_text())["seconds"]
    except (OSError, ValueError, KeyError):
        return 60


def in_subprocess(name):
    """One test in its own process; its report (report.json) is what counts."""
    from coop_env import TOOLS
    out = TOOLS["out"] / name
    out.mkdir(parents=True, exist_ok=True)
    report = out / "report.json"
    started = time.time()
    with open(out / "log.txt", "w") as log:
        try:
            subprocess.run([sys.executable, os.path.abspath(__file__), "--one", name], stdout=log,
                           stderr=subprocess.STDOUT, timeout=TEST_TIMEOUT, cwd=os.path.dirname(os.path.abspath(__file__)))
        except subprocess.TimeoutExpired:
            return {"passed": False, "error": f"timed out after {TEST_TIMEOUT} s", "checks": [],
                    "seconds": TEST_TIMEOUT}
    try:
        r = json.loads(report.read_text())
        if report.stat().st_mtime >= started:
            return r
    except (OSError, ValueError):
        pass
    return {"passed": False, "error": f"no report: the test's process died (see {out / 'log.txt'})",
            "checks": [], "seconds": round(time.time() - started, 1)}


def run_parallel(names, jobs):
    from module import maria_blob
    maria_blob()  # built once here, not by several tests at once
    lanes, alone = [], []
    network = [n for n in names if module_of(n) in NETWORK_MODULES]
    if network:
        lanes.append(network)
    chained = {n for chain in CHAINS for n in chain}
    for chain in CHAINS:
        if any(n in names for n in chain):
            lanes.append([n for n in chain if n in names])
    solo = [n for n in names if n in SOLO]
    taken = set(network) | chained | set(solo)
    lanes += [[n] for n in names if n not in taken]
    lanes.sort(key=lambda lane: -sum(last_seconds(n) for n in lane))
    results, lock, queue = {}, threading.Lock(), list(lanes)
    t0 = time.time()

    def worker():
        while True:
            with lock:
                if not queue:
                    return
                lane = queue.pop(0)
            for name in lane:
                r = in_subprocess(name)
                with lock:
                    results[name] = r
                    print(f"[{len(results)}/{len(names)} {time.time() - t0:.0f}s] " + show(r, name), flush=True)

    threads = [threading.Thread(target=worker) for _ in range(min(jobs, len(lanes)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for name in solo:
        r = in_subprocess(name)
        results[name] = r
        print(f"[{len(results)}/{len(names)} {time.time() - t0:.0f}s, alone] " + show(r, name), flush=True)
    failed = [n for n in names if not results[n]["passed"]]
    print(f"\n{len(names) - len(failed)} of {len(names)} passed in {time.time() - t0:.0f} s ({jobs} at once)")
    for n in failed:
        print(f"FAIL {n}")
    return failed


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--one"]:  # a worker: one test, here
        sys.exit(0 if run_one(args[1])["passed"] else 1)
    jobs = max(1, (os.cpu_count() or 2) - 4)  # a few cores left for the PC's own use
    full = "--full" in args
    if "-j" in args:
        k = args.index("-j")
        jobs = int(args[k + 1])
        del args[k:k + 2]
    names = [a for a in args if not a.startswith("--")]
    if not names:
        names = list(SCENARIOS) + list(SESSION_SCENARIOS)
        if not full:
            names = [n for n in names if not n.endswith(LONG)]
    if jobs > 1 and len(names) > 1:
        sys.exit(1 if run_parallel(names, jobs) else 0)
    failed = 0
    for name in names:
        r = run_one(name)
        failed += not r["passed"]
        print(show(r, name))
    sys.exit(1 if failed else 0)
