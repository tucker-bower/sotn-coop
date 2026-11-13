"""Widescreen's edge check (design/M19-widescreen.md): in each debug start, at a view width, what
the stage's entities do at the edges of the wider view.

    python widescreen_edges.py [--width 448] [--frames 900] [--raw] [name ...]

The player walks right, then left, across the room. Each frame, for each stage entity:
- pop-in: an entity appears well inside the view, in its extra width (spawned where the player can
  see it, and couldn't at 4:3);
- vanish: one disappears there without dying (destroyed where it can be seen);
- frozen: one well inside the view, outside the game's own 256 view, that hasn't moved or animated
  for FROZEN frames (it may just be idle: these are candidates, to look at).
--raw turns the module's stage windows off (widescreen_stage.c), to see what they fix.
Frames around a room change are left out (everything reloads). Prints one line per start, and
the totals. A start's state holds the module: rebuild them
(scripts/rebuild_fixtures.sh) after changing it."""

import argparse
import struct
import sys
from pathlib import Path

from session import Session  # noqa: F401 (puts `link` on the path)

from bots import walker
from coop_env import TOOLS
from emu import Emu
from module import COOP_DISC, symbols

STARTS = TOOLS["out"].parent / "fixtures" / "debug-starts"
ENTITY, FIRST, LAST = 0xBC, 64, 256  # g_Entities: size, STAGE_ENTITY_START, TOTAL_ENTITY_COUNT
INSIDE = 24     # px from the view's edges: "well inside"
FROZEN = 90     # frames unchanged
DEAD = 0x100    # FLAG_DEAD


def entities(e):
    raw = e.read_bytes("g_Entities", ENTITY * LAST)
    out = {}
    for slot in range(FIRST, LAST):
        b = raw[slot * ENTITY:(slot + 1) * ENTITY]
        eid = struct.unpack_from("<H", b, 0x26)[0]
        if eid:
            x, y = struct.unpack_from("<h", b, 2)[0], struct.unpack_from("<h", b, 6)[0]
            flags, hp = struct.unpack_from("<I", b, 0x34)[0], struct.unpack_from("<h", b, 0x3E)[0]
            state = b[0:8] + b[0x50:0x58]  # position, pose and animation
            out[slot] = (eid, x, y, flags, hp, state)
    return out


def check(name, width, frames, raw):
    sym = symbols()
    found = {"pop-in": [], "vanish": [], "frozen": []}
    with Emu(str(COOP_DISC)) as e:
        e.load_state_file(str(STARTS / f"{name}.state"))
        e.write(sym["g_CoopWideWidth"], width, "<H")
        if raw:
            e.write(sym["g_CoopWideStageOff"], 1, "<B")
        e.step(10)
        before, still, room, quiet = entities(e), {}, e.snapshot()["room"], 0
        bots = [walker("right", attack_every=0), walker("left", attack_every=0)]
        for i in range(frames):
            bot = bots[(i * 2) // frames]
            e.step(1, bot(e.snapshot(), i))
            slide = e.read(sym["g_CoopWideSlide"], "<i")
            lo, hi = -slide + INSIDE, width - slide - INSIDE  # the view, in the game's screen x
            now = entities(e)
            if e.snapshot()["room"] != room:  # a room change reloads everything: not the edges'
                room, quiet = e.snapshot()["room"], 30
            if quiet:
                quiet -= 1
                before, still = now, {}
                continue
            for slot, (eid, x, y, flags, hp, state) in now.items():
                inside = lo <= x < hi and 20 + INSIDE <= y < 227 - INSIDE and not 0 <= x < 256  # the margins
                was = before.get(slot)
                if inside and (not was or was[0] != eid):
                    found["pop-in"].append((i, slot, hex(eid), x, y))
                outer = inside and not (-64 <= x < 320)
                if outer and was and was[5] == state:
                    still[slot] = still.get(slot, 0) + 1
                    if still[slot] == FROZEN:
                        found["frozen"].append((i, slot, hex(eid), x, y))
                else:
                    still.pop(slot, None)
            for slot, (eid, x, y, flags, hp, state) in before.items():
                if (slot not in now and lo <= x < hi and not 0 <= x < 256 and 20 + INSIDE <= y < 227 - INSIDE
                        and not flags & DEAD and hp > 0):
                    found["vanish"].append((i, slot, hex(eid), x, y))
            before = now
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--width", type=int, default=448)
    ap.add_argument("--frames", type=int, default=900)
    ap.add_argument("--raw", action="store_true")
    args = ap.parse_args()
    names = args.names or sorted(p.stem for p in STARTS.glob("*.state"))
    totals = {"pop-in": 0, "vanish": 0, "frozen": 0}
    for name in names:
        found = check(name, args.width, args.frames, args.raw)
        for k in totals:
            totals[k] += len(found[k])
        print(f"{name:40} " + "  ".join(f"{k} {len(v):3}" for k, v in found.items())
              + "".join(f"\n    {k}: {v[:4]}" for k, v in found.items() if v))
    print(f"\n{len(names)} starts at {args.width}{' (raw)' if args.raw else ''}: "
          + ", ".join(f"{v} {k}" for k, v in totals.items()))


if __name__ == "__main__":
    sys.exit(main())
