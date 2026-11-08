#!/usr/bin/env python3
"""Makes Saturn Maria's patch (docs/design/character-mods.md): what turns the player's own discs
into her overlay. Her code ships; her art doesn't. Every array launcher/saturn_maria.py makes
from the Saturn disc is zeroed in her build ("hollow", as SOTN Ultimate's own release does), and
the patch is from the PS1 disc's RIC.BIN (Richter's art she keeps comes from there) to that.

    make_patches.py <out folder>     (after `make -C characters/maria-saturn`)

Writes sat-maria.bps, sat-maria-partner.bps (her partner build, the same way) and sat-maria.json:
where each array goes in each (offset, size, MD5), and the MD5 of each Saturn file the converter
reads, to check the player's disc. Needs the dev
machine's Saturn disc in disks/saturn (LOCAL.md).
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "patcher"))
sys.path.insert(0, str(REPO / "launcher"))
import bps  # noqa: E402
import saturn_maria  # noqa: E402

ROOT = REPO / ".env/src/sotn-decomp"
BUILD = ROOT / "build/coop/maria-saturn"
SATURN = ROOT / "disks/saturn"
RIC = ROOT / "disks/us/BIN/RIC.BIN"
SLOT = 0x8013C000  # her file's first byte (sat_maria.ld)
PARTNER_SLOT = 0x80200000  # her partner build's (sat_maria_partner.ld; module/coop_api.h PARTNER_SAT_ADDR)
SATURN_FILES = ("MARIA.PRG", "MARIA.CHR", "MAR_W.CHR", "0.BIN", "STAGE_01.CHR")


def md5(b):
    return hashlib.md5(b).hexdigest()


def symbols(elf):
    """{name: [(address, size)]} from nm."""
    out = {}
    nm = subprocess.run(["mipsel-linux-gnu-nm", "-S", str(elf)], capture_output=True, text=True, check=True)
    for line in nm.stdout.splitlines():
        p = line.split()
        if len(p) == 4:
            out.setdefault(p[3], []).append((int(p[0], 16), int(p[1], 16)))
    return out


def hollow(ovl, elf, arrays, slot=SLOT):
    """Her file with every array zeroed, and {name: [offset, size, md5]}."""
    syms, out, where = symbols(elf), bytearray(ovl), {}
    for name, data in sorted(arrays.items()):
        found = syms.get(name)
        if not found or len(found) != 1:
            raise SystemExit(f"{name}: {len(found or [])} symbols of that name in her build")
        addr, size = found[0]
        at = addr - slot
        if size != len(data) or ovl[at:at + size] != data:
            raise SystemExit(f"{name}: the build's bytes aren't the converter's (rebuild her art?)")
        out[at:at + size] = bytes(size)
        where[name] = [at, size, md5(data)]
    return bytes(out), where


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    files = {n: (SATURN / n).read_bytes() for n in SATURN_FILES}
    arrays = saturn_maria.arrays(files.__getitem__, lambda p: (ROOT / "disks/us" / p).read_bytes())
    ovl, where = hollow((BUILD / "SATMAR.BIN").read_bytes(), BUILD / "satmar.elf", arrays)
    povl, pwhere = hollow((BUILD / "SATMARP.BIN").read_bytes(), BUILD / "satmarp.elf", arrays, PARTNER_SLOT)
    src = RIC.read_bytes()
    stored = []
    for name, target in (("sat-maria.bps", ovl), ("sat-maria-partner.bps", povl)):
        patch = bps.create_moving(src, target, report=stored)
        assert bps.apply(src, patch) == target
        (out / name).write_bytes(patch)
    about = {"source": "BIN/RIC.BIN", "size": len(ovl), "partner_size": len(povl), "stored": sum(n for _, n in stored),
             "saturn_files": {n: md5(b) for n, b in files.items()}, "arrays": where,
             "partner_arrays": {n: w[0] for n, w in pwhere.items()}}
    (out / "sat-maria.json").write_text(json.dumps(about, indent=1))
    print(f"sat-maria.bps and -partner.bps: {about['stored']} of {len(ovl) + len(povl)} bytes not from the disc, "
          f"{len(where)} arrays ({sum(w[1] for w in where.values())} bytes) left for the launcher")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else REPO / ".env/out/maria")
