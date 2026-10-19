#!/usr/bin/env python3
"""Checks that every file of the retail disc sits at the same sector on the co-op disc.

    check_disc_layout.py retail.cue coop.cue

The game plays its FMVs (and maybe more) from fixed sector positions, so moving any retail
file breaks it. Files the mod adds may only go after them. Exit code 0 = layout intact.
CD-DA entries (*.DA) are skipped: they point into the audio track, which upstream's own
mastering already places differently, and the game plays them by track, not by sector.
"""

import struct
import sys
from pathlib import Path

SECTOR, DATA = 2352, 24  # raw Mode 2 sectors: user data starts after sync, header and subheader


def bin_path(cue):
    for line in Path(cue).read_text().splitlines():
        if line.strip().startswith("FILE"):
            return Path(cue).parent / line.split('"')[1]
    raise SystemExit(f"no FILE line in {cue}")


def files(image):
    """{path: (lba, size)} for every file in the ISO 9660 tree."""
    data = image.read_bytes()

    def sector(n):
        return data[n * SECTOR + DATA:n * SECTOR + DATA + 2048]

    out = {}

    def walk(lba, size, prefix):
        blob = b"".join(sector(lba + i) for i in range((size + 2047) // 2048))
        i = 0
        while i < len(blob):
            n = blob[i]
            if n == 0:  # records don't cross sectors: skip to the next one
                i = (i // 2048 + 1) * 2048
                continue
            ext, length, flags = struct.unpack_from("<I", blob, i + 2)[0], struct.unpack_from("<I", blob, i + 10)[0], blob[i + 25]
            name = blob[i + 33:i + 33 + blob[i + 32]]
            if name not in (b"\0", b"\1"):
                path = prefix + name.decode()
                if flags & 2:
                    walk(ext, length, path + "/")
                else:
                    out[path] = (ext, length)
            i += n

    root = sector(16)[156:156 + 34]
    walk(struct.unpack_from("<I", root, 2)[0], struct.unpack_from("<I", root, 10)[0], "")
    return out


def main():
    retail, coop = ({p: v for p, v in files(bin_path(c)).items() if not p.endswith(".DA;1")}
                    for c in sys.argv[1:3])
    moved = [f"{p}: sector {retail[p][0]} -> {coop.get(p, ('missing',))[0]}"
             for p in retail if coop.get(p, (None,))[0] != retail[p][0]]
    last = max(lba + (size + 2047) // 2048 for lba, size in retail.values())
    added = {p: v for p, v in coop.items() if p not in retail}
    early = [p for p, (lba, _) in added.items() if lba < last]
    for line in moved + [f"{p}: added before the end of the retail files" for p in early]:
        print(line)
    print(f"{len(retail)} retail files, {len(moved)} moved; added: {', '.join(added) or 'none'}")
    sys.exit(1 if moved or early else 0)


if __name__ == "__main__":
    main()
