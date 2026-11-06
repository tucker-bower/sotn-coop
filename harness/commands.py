"""Tests that are programs of their own, run by run.py beside the scenarios: the launcher's checks
(no game), its UI flows (launcher/uxdriver.py: the real app, headless) and the patcher's round
trip. One passes when its program exits 0; its output is .env/out/<name>/log.txt, a UI flow's
screens in .env/out/<name>/flow."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI_FLOWS = ("randomizer", "solo", "couch", "characters", "startup", "test_castles", "boss_rush", "hud", "window", "menus", "report_send", "crash")

COMMANDS = {}  # name -> (argv, extra environment); "{out}" in argv: the test's out folder
for _f in sorted((ROOT / "launcher").glob("test_*.py")):
    COMMANDS["launcher_" + _f.stem[len("test_"):]] = ([str(_f)], {})
for _f in sorted((ROOT / "link").glob("test_*.py")):  # the NAT matrix and router port mapping, no games
    COMMANDS["link_" + _f.stem[len("test_"):]] = ([str(_f)], {})
COMMANDS["patcher_round_trip"] = ([str(ROOT / "patcher" / "test_patcher.py")], {})
COMMANDS["patcher_layer"] = ([str(ROOT / "patcher" / "test_layer.py")], {})
for _flow in UI_FLOWS:
    COMMANDS["ui_" + _flow] = ([str(ROOT / "launcher" / "uxdriver.py"), _flow, "--out", "{out}"], {})
COMMANDS["ui_online"] = ([str(ROOT / "launcher" / "uxdriver.py"), "online", "--out", "{out}"], {})
COMMANDS["ui_online_boss_rush"] = (COMMANDS["ui_online"][0], {"COOP_UX_RUSH": "1"})


def run_command(name):
    """Runs it (each in a fresh data folder: never the player's), writes its report.json."""
    from coop_env import TOOLS
    argv, extra = COMMANDS[name]
    out = TOOLS["out"] / name
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="coop-test-", ignore_cleanup_errors=True) as data:
        env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy", COOP_DATA=data, **extra)
        p = subprocess.run([sys.executable] + [a.replace("{out}", str(out / "flow")) for a in argv], env=env,
                           cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sys.stdout.write(p.stdout)
    tail = "\n".join([line for line in p.stdout.splitlines() if not line.startswith("[")][-12:])
    r = {"passed": p.returncode == 0, "seconds": round(time.time() - started, 1), "checks": [],
         "error": None if p.returncode == 0 else f"exit {p.returncode}:\n{tail}"}
    (out / "report.json").write_text(json.dumps(r, indent=1))
    return r
