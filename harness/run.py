#!/usr/bin/env python3
"""Runs harness scenarios.  python run.py [scenario ...]   (no args: all). Exit code 0 = all passed."""

import sys

import scenarios  # noqa: F401  (registers scenarios)
from scenario import SCENARIOS, run_scenario

names = sys.argv[1:] or list(SCENARIOS)
failed = 0
for name in names:
    r = run_scenario(name)
    failed += not r["passed"]
    rooms = " -> ".join(f"{x['room'][0]},{x['room'][1]}" for x in r["rooms"])
    print(f"{'PASS' if r['passed'] else 'FAIL'} {name}: {r['frames']} frames in {r['seconds']}s; rooms {rooms}")
    for c in r["checks"]:
        print(f"   {'ok ' if c['ok'] else 'BAD'} {c['what']}")
    if r["error"]:
        print("   " + r["error"].strip().replace("\n", "\n   "))
sys.exit(1 if failed else 0)
