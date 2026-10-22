#!/usr/bin/env python3
"""Checks that every DRA symbol of the co-op build sits at its retail address (D33).

    check_dra_symbols.py retail-dra.map coop-dra.map

The module calls DRA's static functions by address, and DRA's fixed-address data must not move,
so a co-op hook may change code but never the layout. DRA's end address alone doesn't prove it:
a hook that shrinks one function shifts every later one while the image still ends in place.
Exit code 0 = layout intact.
"""

import re
import sys

SYMBOL = re.compile(r"\s+0x([0-9a-f]+)\s+([A-Za-z_]\w*)\s*$")


def symbols(path):
    out = {}
    for line in open(path):
        m = SYMBOL.match(line)
        if m:
            out[m.group(2)] = int(m.group(1), 16)
    return out


def main(retail, coop):
    a, b = symbols(retail), symbols(coop)
    moved = [f"{k}: {a[k]:#x} -> {b[k]:#x}" for k in a if k in b and a[k] != b[k]]
    missing = sorted(set(a) - set(b))
    if moved or missing or not a:
        print(f"DRA's layout changed ({len(moved)} moved, {len(missing)} missing of {len(a)}):", file=sys.stderr)
        for line in (moved + missing)[:20]:
            print("  " + line, file=sys.stderr)
        return 1
    print(f"{len(a)} DRA symbols, none moved")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
