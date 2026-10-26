"""Which parts of VRAM do the stages use? (design/M12: Maria's guardians share VRAM with the hand
weapons' graphics, playtest 2026-10-25 note 4; a spot for one of them must be free everywhere.)

    python vram_survey.py [state ...]      (default: the savestate library and the debug starts)

The core doesn't expose VRAM, but its savestates hold it raw: found once by looking for a row of
the screen in a state. Prints a map of 64x32-word blocks: '.' never written in any state, '#' used.
"""

import struct
import sys
from pathlib import Path

from coop_env import TOOLS, savestate
from emu import Emu
from module import COOP_DISC

VRAM_W, VRAM_H = 1024, 512
BLOCK_W, BLOCK_H = 64, 32
_base = None


def _find_base(e):
    st = bytes(e.save_state())
    w, h, fmt, pitch, data = e.raw_frame()
    for row in (200, 60, 120):  # a row that's in VRAM's first framebuffer (y = row)
        px = struct.unpack_from("<%dH" % w, data, row * pitch)
        conv = [((p >> 11) & 31) | (((p >> 6) & 31) << 5) | ((p & 31) << 10) for p in px]
        pat = struct.pack("<16H", *conv[100:116])
        i = st.find(pat)
        while i >= 0:
            base = i - 2 * (100 + VRAM_W * row)
            if base >= 0 and st[base + 2 * (100 + VRAM_W * row):][:32] == pat:
                return base
            i = st.find(pat, i + 1)
    raise RuntimeError("VRAM not found in the savestate")


def vram(e):
    """This game's VRAM now: 1024x512 16-bit words, row by row."""
    global _base
    if _base is None:
        _base = _find_base(e)
    st = bytes(e.save_state())
    return st[_base:_base + VRAM_W * VRAM_H * 2]


def used_blocks(v):
    out = set()
    for by in range(VRAM_H // BLOCK_H):
        for bx in range(VRAM_W // BLOCK_W):
            for y in range(by * BLOCK_H, (by + 1) * BLOCK_H):
                o = 2 * (y * VRAM_W + bx * BLOCK_W)
                if any(v[o:o + 2 * BLOCK_W]):
                    out.add((bx, by))
                    break
    return out


def survey(states):
    used = set()
    with Emu(COOP_DISC) as e:
        for s in states:
            e.load_state_file(s)
            e.step(120)  # let the stage finish its uploads
            used |= used_blocks(vram(e))
    return used


def show(used):
    print("     x: " + "".join(f"{bx * BLOCK_W:<4x}"[:1] for bx in range(VRAM_W // BLOCK_W)))
    for by in range(VRAM_H // BLOCK_H):
        print(f"y {by * BLOCK_H:03x}: " + "".join("#" if (bx, by) in used else "." for bx in range(VRAM_W // BLOCK_W)))


def default_states():
    lib = savestate(COOP_DISC, "x").parent
    starts = TOOLS["out"].parent / "fixtures" / "debug-starts"
    return sorted(lib.glob("*.state")) + sorted(starts.rglob("*.state"))


if __name__ == "__main__":
    states = [Path(a) for a in sys.argv[1:]] or default_states()
    print(f"{len(states)} states")
    show(survey(states))
