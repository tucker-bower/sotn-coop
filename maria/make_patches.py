#!/usr/bin/env python3
"""Makes Maria's patches (design/M8 §4): what turns the player's own Dracula X Chronicles (USA)
files into our Maria. They hold our code and our build's pointer tables, never her art, voice
or palettes, which the patches copy from the player's disc (checked here: see `stored`).

    make_patches.py <out folder>     (after `make -C maria`)

Writes maria.bps and maria-partner.bps (from PSP_GAME/USRDIR/res/ps/PSPBIN/maria.bin), maria-vh.bps and maria-vb.bps
(from PSP_GAME/USRDIR/res/ps/snd_e/SE/sd_mar2.spk) and maria.json (what the launcher checks).
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "patcher"))
import bps  # noqa: E402

ROOT = HERE.parent / ".env/src/sotn-decomp"
DXC = ROOT / "disks/pspus/PSP_GAME/USRDIR/res/ps"
BUILD = ROOT / "build/coop/maria"
SOURCES = {"maria.bin": "PSPBIN/maria.bin", "sd_mar2.spk": "snd_e/SE/sd_mar2.spk"}
PATCHES = [("maria.bps", "maria.bin", "MARIA.BIN"),
           ("maria-partner.bps", "maria.bin", "MARIAP.BIN"),  # her as the partner (design/M13 step 3)
           ("maria-vh.bps", "sd_mar2.spk", "sfx/SD_RIH.VH"),
           ("maria-vb.bps", "sd_mar2.spk", "sfx/SD_RIH.VB")]


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    about = {"sources": SOURCES, "patches": {}}
    for name, source, target in PATCHES:
        src = (DXC / SOURCES[source]).read_bytes()
        tgt = (BUILD / target).read_bytes()
        stored = []
        patch = bps.create_moving(src, tgt, report=stored)
        assert bps.apply(src, patch) == tgt
        (out / name).write_bytes(patch)
        about["patches"][name] = {"source": source, "target": Path(target).name, "size": len(tgt),
                                  "stored": sum(n for _, n in stored)}
        print(f"{name}: {len(patch)} bytes; {about['patches'][name]['stored']} of {len(tgt)} not from the disc")
    (out / "maria.json").write_text(json.dumps(about, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else HERE.parent / ".env/out/maria")
