"""Replays an F9 bug report (a zip from the launcher's reports folder) in the harness.

    python replay.py <report.zip> [--from N]

Loads both games' states from the oldest in-memory checkpoint in before/ (or the one at frame
N), replays both pads' recorded inputs up to the moment F9 was pressed, and saves both screens
every 10 frames next to the zip (<report>-replay/). The link between the games isn't
deterministic in the launcher (two processes, UDP), so a replay can differ a little from what
was seen; now/*.state are the exact moment, for inspecting RAM."""

import argparse
import json
import struct
import tempfile
import zipfile
from pathlib import Path

from session import Session  # first: puts `link` on the path

from module import COOP_DISC


def loadable(state, disc):
    """A report's state, with this machine's disc: the report blanks its path, in the state's
    header and in the trailer after its data (docs/research.md)."""
    b, path = bytearray(state), str(Path(disc).resolve()).encode()
    title, name_length, data_size = 8 + 8, 8 + 168, 8 + 208
    size, offset = struct.unpack_from("<II", b, data_size)
    b[title:title + 128] = path.ljust(128, b"\0")
    struct.pack_into("<II", b, name_length, len(path), 8)
    b[8 + offset + size:8 + offset + size + 8] = bytes(8)  # the trailer
    return bytes(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report", type=Path)
    ap.add_argument("--from", dest="start", type=int)
    ap.add_argument("--disc", default=str(COOP_DISC), help="the co-op disc the report was made on")
    args = ap.parse_args()
    z = zipfile.ZipFile(args.report)
    names = z.namelist()
    frames = sorted({int(n.split("/")[1].split("_")[0]) for n in names if n.startswith("before/")})
    inputs = json.loads(z.read("inputs.json"))
    start = args.start if args.start is not None else (frames[0] if frames else None)
    tmp = Path(tempfile.mkdtemp(prefix="coop-replay-"))
    if start is None:
        files = ("now/A.state", "now/B.state")
        todo = []
    else:
        files = (f"before/{start}_A.state", f"before/{start}_B.state")
        last = max((f for f, _, _ in inputs), default=start)
        todo = [(pa, pb) for f, pa, pb in inputs if start <= f <= last]
    starts = []
    for f in files:
        (tmp / Path(f).name).write_bytes(loadable(z.read(f), args.disc))
        starts.append(str(tmp / Path(f).name))
    out = args.report.with_name(args.report.stem + "-replay")
    out.mkdir(exist_ok=True)
    with Session(args.disc, starts=tuple(starts)) as s:
        for k, pads in enumerate(todo):
            s.step(1, p1=pads)
            if k % 10 == 0:
                from PIL import Image
                a, b = s.a.screenshot(), s.b.screenshot()
                img = Image.new("RGB", (a.width + b.width + 4, a.height))
                img.paste(a, (0, 0))
                img.paste(b, (a.width + 4, 0))
                img.save(out / f"{k:05d}.png")
    print(f"replayed {len(todo)} frames from {start}: {out}")


if __name__ == "__main__":
    main()
