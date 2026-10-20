#!/usr/bin/env python3
"""Runs harness scenarios.  python run.py [scenario ...]   (no args: all but the long *_NNmin soaks,
which run by name). Exit code 0 = all passed."""

import sys

import scenarios  # noqa: F401  (registers scenarios)
import session_scenarios  # noqa: F401
import session_progress  # noqa: F401
import session_travel  # noqa: F401
import session_saverooms  # noqa: F401
import session_shared  # noqa: F401
import session_m4b  # noqa: F401
import session_m5  # noqa: F401
import session_online  # noqa: F401
import spec_test  # noqa: F401
from scenario import SCENARIOS, run_scenario
from session import SESSION_SCENARIOS, run_session_scenario

if __name__ == "__main__":
    names = sys.argv[1:] or list(SCENARIOS) + [n for n in SESSION_SCENARIOS if not n.endswith("min")]
    failed = 0
    for name in names:
        r = run_session_scenario(name) if name in SESSION_SCENARIOS else run_scenario(name)
        failed += not r["passed"]
        rooms = " -> ".join(f"{x['room'][0]},{x['room'][1]}" for x in r.get("rooms", []))
        detail = f"{r['frames']} frames in {r['seconds']}s; rooms {rooms}" if "frames" in r else f"{r['seconds']}s, two games"
        print(f"{'PASS' if r['passed'] else 'FAIL'} {name}: {detail}")
        for c in r["checks"]:
            print(f"   {'ok ' if c['ok'] else 'BAD'} {c['what']}")
        if r["error"]:
            print("   " + r["error"].strip().replace("\n", "\n   "))
    sys.exit(1 if failed else 0)
