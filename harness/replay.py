"""Replays a launcher bookmark (F9 in the playtest launcher) in the harness.

    python replay.py <bookmark dir> [--from N]

Loads both games' states from the oldest checkpoint (or the one at frame N), replays both pads'
recorded inputs up to the moment F9 was pressed, and saves both screens every 10 frames in
<bookmark dir>/replay/ (and a contact sheet). The link between the games isn't deterministic
in the launcher (two processes, UDP), so a replay can differ a little from what was seen; the
"*_now.state" files are the exact moment, for inspecting RAM."""

import argparse
import json
from pathlib import Path

from session import Session  # first: puts `link` on the path

from module import COOP_DISC


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bookmark", type=Path)
    ap.add_argument("--from", dest="start", type=int)
    args = ap.parse_args()
    info = json.loads((args.bookmark / "info.json").read_text())
    start = args.start if args.start is not None else min(info["states"], default=None)
    if start is None:
        starts = (args.bookmark / "A_now.state", args.bookmark / "B_now.state")
        inputs = []
    else:
        starts = (args.bookmark / f"A_{start}.state", args.bookmark / f"B_{start}.state")
        inputs = [(pa, pb) for f, pa, pb in info["inputs"] if start <= f < info["frame"]]
    out = args.bookmark / "replay"
    out.mkdir(exist_ok=True)
    with Session(COOP_DISC, starts=tuple(str(x) for x in starts)) as s:
        shots = []
        for k, pads in enumerate(inputs):
            s.step(1, p1=pads)
            if k % 10 == 0:
                a, b = s.a.screenshot(), s.b.screenshot()
                shots.append((k, a, b))
        from PIL import Image
        for k, a, b in shots:
            img = Image.new("RGB", (a.width + b.width + 4, a.height))
            img.paste(a, (0, 0))
            img.paste(b, (a.width + 4, 0))
            img.save(out / f"{k:05d}.png")
        print(f"replayed {len(inputs)} frames from {start}: {len(shots)} shots in {out}")


if __name__ == "__main__":
    main()
