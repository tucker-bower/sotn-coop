#!/usr/bin/env python3
"""Makes the harness's debug, boss and scene starts (launcher/debugstarts.py) from the co-op disc,
into .env/fixtures/debug-starts (session_m12.STARTS). Game RAM: never committed."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "harness"), str(ROOT / "launcher"), str(ROOT)]
import debugstarts  # noqa: E402
from module import COOP_DISC  # noqa: E402

if __name__ == "__main__":
    proc, q = debugstarts.start(COOP_DISC, str(ROOT / ".env/fixtures/debug-starts"))
    while True:
        kind, step, steps, text = q.get()
        if kind in ("done", "error"):
            print(kind, step, steps, text, flush=True)
            break
    proc.join()
    sys.exit(kind != "done")
