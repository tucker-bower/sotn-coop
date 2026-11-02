"""Richter's and Maria's cutscene portraits, read from the player's disc for their pause menu
(module/portrait.c). The host puts them in expansion RAM: reading them at boot took 1.2 s.

    read(disc) -> bytes for PORTRAIT_ADDR, or None (their menu then keeps Alucard's picture)
"""

import mmap
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patcher"))

PORTRAIT_ADDR, PORTRAIT_MAGIC = 0x806C4000, 0x54524F50  # 'PORT' (module/coop_api.h)
RAW_SECTOR, HEADER, DATA = 2352, 24, 2048
PIXELS, PALETTE = 48 * 72, 128 * 2
PARTS = (("ST/ST0/ST0.BIN", 0xF130, 0x1A830), ("ST/DAI/DAI.BIN", 0x139E4, 0x1760C))  # Richter's, Maria's


def track(disc):
    """The data track of a .cue, or the disc itself."""
    disc = Path(disc)
    if disc.suffix.lower() != ".cue":
        return disc
    return disc.parent / re.search(r'FILE\s+"([^"]+)"', disc.read_text(errors="replace")).group(1)


def _span(image, first, offset, size):
    out = b""
    while size:
        sector, at = first + offset // DATA, offset % DATA
        n = min(size, DATA - at)
        start = sector * RAW_SECTOR + HEADER + at
        out += image[start:start + n]
        offset, size = offset + n, size - n
    return out


def read(disc):
    from patcher import find_file
    try:
        with open(track(disc), "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as image:
            out = PORTRAIT_MAGIC.to_bytes(4, "little")
            for path, pixels, palette in PARTS:
                first = find_file(image, path)[0]
                out += _span(image, first, pixels, PIXELS) + _span(image, first, palette, PALETTE)
            return out
    except (OSError, ValueError, TypeError, AttributeError):
        return None
