#!/usr/bin/env python3
"""Runs the tests: the harness scenarios (one game, two linked games) and the programs in
commands.py (launcher checks, UI flows, the patcher).

    python run.py [-j N] [--full] [--again] [--list] [-c CATEGORY ...] [--changed] [-k WORD ...] [name ...]
    python run.py --history

Pick the smallest that covers the change (AGENTS.md, Testing; categories.py):
- -c CATEGORY (again for more): every test in it, e.g. `run.py -c richter` after a change to
  Richter's code. --changed picks the categories from the files this branch changed;
- names, or -k WORD: the tests you're working on;
- nothing: the PR gate (categories.EVERYDAY), before opening or updating a PR;
- --full: everything, before a release. With -c or -k it adds their full-only tests.
A test whose last run passed after the disc and the sources last changed is skipped: it would
pass again (--again runs it anyway). So --full after the gate runs only the rest.
--list prints the chosen tests (tier, categories, last time) without running them. --history
prints each test's runs and failures from .env/out/history.jsonl, which every run adds to.
Tests run side by side, each in its own process (-j: how many at once; default the cores less 4,
12 on a 16-core PC; -j 1 runs them one after another in this process). The tests that time the
host in real time (SOLO) run after the rest, side by side with each other only. Each test's output
goes to .env/out/<name>/log.txt. Exit code 0 = all passed."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time

os.environ.setdefault("COOP_NO_PORTMAP", "1")  # tests never ask the real router to open a port (M14)
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
import session_rooms  # noqa: F401
import session_m9  # noqa: F401
import session_m11  # noqa: F401
import session_m12  # noqa: F401
import scenarios_m12  # noqa: F401
import scenarios_relics  # noqa: F401
import scenarios_movement  # noqa: F401
import scenarios_m13  # noqa: F401
import scenarios_ultimate  # noqa: F401
import session_m15  # noqa: F401
import session_rules  # noqa: F401
import session_carry  # noqa: F401
import session_inverted  # noqa: F401
import session_inverted_rooms  # noqa: F401
import session_crawl  # noqa: F401
import session_edges  # noqa: F401
import session_bossrush  # noqa: F401
import session_netplay  # noqa: F401
import session_mods  # noqa: F401
import spec_test  # noqa: F401
import categories
from commands import COMMANDS, run_command
from scenario import FULL_ONLY, SCENARIOS, run_scenario
from session import SESSION_SCENARIOS, run_session_scenario

# Tests that use real sockets, a room-code relay or LAN broadcasts (fixed port 47811): one at a
# time, in their own lane, so two of them never hear each other.
NETWORK_MODULES = {"session_online", "session_m9", "session_m11", "spec_test"}
NETWORK = {"ui_online", "ui_online_boss_rush"}
# Tests that run in real time (the host's p99 per frame, the app's first picture, two launchers
# online): after the rest, side by side with each other only, as a full machine's load would be
# in their numbers (2026-10-31: ui_online_boss_rush's joiner stayed at the title under full load).
SOLO = {"mixed_soak_short", "mixed_soak_10min", "mixed_soak_baseline_10min", "ui_startup", "ui_online",
        "ui_online_boss_rush"}
# Tests that read another's output: (first, then) run in that order, in one lane.
CHAINS = [("mixed_soak_baseline_10min", "mixed_soak_10min")]
TEST_TIMEOUT = 1800  # seconds: a test that hangs fails instead of holding up the run


ALL = list(SCENARIOS) + list(SESSION_SCENARIOS) + list(COMMANDS)


def module_of(name):
    if name in COMMANDS:
        return "commands"
    fn = SESSION_SCENARIOS[name][0] if name in SESSION_SCENARIOS else SCENARIOS[name][0]
    return fn.__module__


def run_one(name):
    if name in COMMANDS:
        return run_command(name)
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


def make_lanes(names):
    """[[name, ...]]: each lane's tests run one after another, the lanes side by side."""
    lanes = []
    network = [n for n in names if module_of(n) in NETWORK_MODULES or n in NETWORK]
    if network:
        lanes.append(network)
    chained = {n for chain in CHAINS for n in chain}
    for chain in CHAINS:
        if any(n in names for n in chain):
            lanes.append([n for n in chain if n in names])
    lanes += [[n] for n in names if n not in set(network) | chained]
    return sorted(lanes, key=lambda lane: -sum(last_seconds(n) for n in lane))  # longest first


def run_parallel(names, jobs):
    from module import maria_blob
    maria_blob()  # built once here, not by several tests at once
    solo = [n for n in names if n in SOLO]
    results, lock = {}, threading.Lock()
    t0 = time.time()
    run_lanes(make_lanes([n for n in names if n not in SOLO]), jobs, results, lock, t0, len(names))
    run_lanes(make_lanes(solo), jobs, results, lock, t0, len(names), " real time")
    record(results)
    failed = [n for n in names if not results[n]["passed"]]
    print(f"\n{len(names) - len(failed)} of {len(names)} passed in {time.time() - t0:.0f} s ({jobs} at once)")
    for n in failed:
        print(f"FAIL {n}")
    return failed


def run_lanes(lanes, jobs, results, lock, t0, total, tag=""):
    queue = list(lanes)

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
                    print(f"[{len(results)}/{total} {time.time() - t0:.0f}s{tag}] " + show(r, name), flush=True)

    threads = [threading.Thread(target=worker) for _ in range(min(jobs, len(lanes)))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


def changed_files():
    """The files this branch changed from main, committed or not."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def git(*a):
        return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True).stdout.split()
    base = (git("merge-base", "main", "HEAD") or ["main"])[0]
    return sorted(set(git("diff", "--name-only", base)) | set(git("ls-files", "--others", "--exclude-standard")))


def choose(args, full):
    """The tests named, matching a -k word, in a -c category or the categories --changed touches; or
    the PR gate; or with --full and nothing else, everything."""
    words = [args[k + 1] for k, a in enumerate(args) if a == "-k"]
    cats = [args[k + 1] for k, a in enumerate(args) if a == "-c"]
    named = [a for k, a in enumerate(args) if not a.startswith("-") and (k == 0 or args[k - 1] not in ("-k", "-c"))]
    unknown = [n for n in named if n not in ALL] + [c for c in cats if c not in categories.CATEGORIES]
    if unknown:
        sys.exit(f"no such test or category: {', '.join(unknown)} (run.py --list shows the tests; "
                 f"categories: {', '.join(categories.CATEGORIES)})")
    modules = set()
    if "--changed" in args:
        touched, modules = categories.for_paths(changed_files())
        for c, files in touched.items():
            print(f"{c}: {', '.join(files[:3])}{' ...' if len(files) > 3 else ''}")
        if modules:
            print(f"test files: {', '.join(sorted(modules))}")
        cats += [c for c in touched if c not in cats]
        if not cats and not modules:
            sys.exit("--changed: no source file this branch changed touches a category (docs only?): nothing to run")
    if not (words or named or cats or modules):
        return list(ALL) if full else [n for n in ALL if n in categories.EVERYDAY]
    tier = [n for n in ALL if full or n not in FULL_ONLY]
    picked = [n for n in tier if any(w in n for w in words) or module_of(n) in modules or
              set(cats) & set(categories.of(n, module_of(n)))]
    return named + [n for n in picked if n not in named]


SOURCES = ("module", "characters", "launcher", "link", "patcher", "harness", "patches")


def build_time():
    """When what the tests run last changed: the disc, or any source file (whichever is newer)."""
    from coop_env import TOOLS
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    newest = 0.0
    disc = TOOLS["out"] / "disc" / "sotn_coop.us.bin"
    if disc.exists():
        newest = disc.stat().st_mtime
    for top in SOURCES:
        for d, _, files in os.walk(os.path.join(root, top)):
            if "__pycache__" in d or "/assets/" in d:
                continue
            for f in files:
                if not f.endswith((".pyc", ".gif", ".png")):
                    newest = max(newest, os.path.getmtime(os.path.join(d, f)))
    return newest


def passed_since_build(names):
    """The tests whose last run passed after the build and the sources last changed: no need to run
    them again (--again does)."""
    from coop_env import TOOLS
    built = build_time()
    done = []
    for n in names:
        report = TOOLS["out"] / n / "report.json"
        try:
            if report.stat().st_mtime > built and json.loads(report.read_text())["passed"]:
                done.append(n)
        except (OSError, ValueError, KeyError):
            pass
    return done


def record(results):
    """Adds each result to .env/out/history.jsonl: what --history (and the gate's upkeep) reads."""
    from coop_env import TOOLS
    failed = sum(not r["passed"] for r in results.values())
    when = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(TOOLS["out"] / "history.jsonl", "a") as f:
        for name, r in results.items():
            f.write(json.dumps({"test": name, "passed": r["passed"], "when": when, "failed_in_run": failed}) + "\n")


def history():
    """Each test's runs and failures. A failure alone (fewer than 9 in its run) is one the test
    caught; a run where many fail is usually a broken build."""
    from coop_env import TOOLS
    stats = {}
    try:
        lines = (TOOLS["out"] / "history.jsonl").read_text().splitlines()
    except OSError:
        lines = []
    for line in lines:
        r = json.loads(line)
        s = stats.setdefault(r["test"], [0, 0, ""])
        s[0] += 1
        if not r["passed"] and r["failed_in_run"] < 9:
            s[1] += 1
            s[2] = r["when"][:10]
    print(f"{'test':55} {'tier':9} {'runs':>5} {'caught':>6}  last caught")
    for n in sorted(ALL, key=lambda n: (-stats.get(n, [0, 0])[1], n)):
        runs, caught, last = stats.get(n, [0, 0, ""])
        tier = "gate" if n in categories.EVERYDAY else "full" if n in FULL_ONLY else "category"
        print(f"{n:55} {tier:9} {runs:5} {caught:6}  {last}")


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
    if "--history" in args:
        history()
        sys.exit(0)
    names = choose(args, full)
    if "--list" in args:
        for n in names:
            tier = "gate" if n in categories.EVERYDAY else "full" if n in FULL_ONLY else "category"
            print(f"{n:55} {tier:9} {last_seconds(n):6.0f} s  {','.join(categories.of(n, module_of(n)))}")
        print(f"{len(names)} tests, {sum(map(last_seconds, names)) / 60:.0f} min one after another")
        loose = [n for n in ALL if not categories.of(n, module_of(n))]
        if loose:
            print(f"in no category (name them so categories.py finds them): {', '.join(loose)}")
        sys.exit(0)
    if not names:
        sys.exit("no test matches")
    if "--again" not in args:
        done = set(passed_since_build(names))
        if done:
            print(f"skipping {len(done)} tests already passed on this build (--again runs them)")
            names = [n for n in names if n not in done]
        if not names:
            sys.exit(0)
    # One folder for all the tests' temporary files, on the disk and gone after: many leave theirs
    # (up to 445 MB each), and they filled a RAM-backed /tmp.
    from coop_env import TOOLS
    TOOLS["out"].mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tmp-run-", dir=TOOLS["out"], ignore_cleanup_errors=True) as tmp:
        os.environ["TMPDIR"] = tmp
        tempfile.tempdir = None
        if jobs > 1 and len(names) > 1:
            sys.exit(1 if run_parallel(names, jobs) else 0)
        failed, results = 0, {}
        for name in names:
            r = results[name] = run_one(name)
            failed += not r["passed"]
            print(show(r, name))
        record(results)
        sys.exit(1 if failed else 0)
