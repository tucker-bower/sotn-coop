#!/usr/bin/env python3
"""Per-overlay facts the co-op module needs at runtime (design/M4-shared-rooms.md).

    gen_overlay_table.py   -> module/overlay_table.c

For every stage and boss overlay of the us build: its stage id, its BSS range and its .data
variables (mirrored to a shared-room guest), and the address and first instruction of each enemy targeting helper
(GetSideToPlayer, GetDistanceToPlayerX/Y), which the module patches in RAM after the overlay
loads. The first instruction lets the module check it's patching the code it expects.
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from coop_env import COOP, REPO as ROOT  # noqa: E402
from gen_flag_gated import stage_ids  # noqa: E402

BUILD = ROOT / "build/us"
OUT = COOP / "module/overlay_table.c"
HELPERS = ("GetSideToPlayer", "GetDistanceToPlayerX", "GetDistanceToPlayerY")
# Scenery a shared-room guest runs itself instead of copying (playtest 1): it draws from the
# camera (3D projection, parallax), so the authority's primitives are wrong for the guest's
# camera. Only pure decoration: nothing here hurts, blocks or is collected. Spawners stay
# copied (their children are scenery, run locally once they appear).
# Red and sealed doors too: they open for the game's own player walking into them, and write
# their tiles after the authority's are copied in, so a guest opens its own (M12: a guest
# Alucard was walled in at Olrox's door until the authority walked through). What locks one
# (NZ1's g_bossDoorsLocked) is one of the overlay's DATA words below, which the guest gets too.
# Camera limits too: they're the limits of one game's own camera, set as its own player walks
# past (playtest 0.14: a guest kept the old limit, and stood on it as if on a floor).
DECOR = re.compile(r"Entity(RedDoor|SealedDoor|LockCamera|Background(Bushes|Trees|PineTrees|Clouds|SkyLand|Lightning|CastleWall|Pillar|"
                   r"Vortex|Bookcase|Furniture|Gears|DoorRubble|Shadow)|Clouds|LightningCloud|"
                   r"DistantBackgroundTrees|ForegroundTree|3DBackgroundHouse|HouseShader|ClockTower3D|"
                   r"StainedGlass|StainedGlassBackground|CavernBackground\w*|NightSky|BgColumnsParallax\w*|"
                   r"DeepBackgroundArch|DistantBookshelves|PurpleBrickScrollingBackground|Fog|DeathSkySwirl|"
                   r"BridgeBackgroundPiece)")
MAX_DECOR = 16
# The layout spawner's cursors (src/st/create_entity.h). A guest's are copies of the
# authority's (they're in the BSS), so a guest that takes the room over re-seats them for its
# own camera (playtest 1: killed wolves came back).
CURSORS = ("g_LayoutObjHorizontal", "g_LayoutObjVertical", "g_LayoutObjPosHorizontal", "g_LayoutObjPosVertical")


# The overlay's state that isn't in its BSS: a variable given a starting value (`s32 g_BossMgrState
# = 0;`) is in its .data, so the BSS copy missed it. A boss fight's state (RBO0's count of fallen
# fakes, which ends the fight; NZ1's g_bossDoorsLocked) stayed the guest's own, and a guest that
# took the room over mid-fight never ended it (issue 248). These are found in the decomp's
# sources: a scalar, not const, defined with a value at file scope; the guest gets their words.
DATA_VAR = re.compile(r"^(?:static\s+)?(?:volatile\s+)?(?:s32|u32|s16|u16|s8|u8|bool|int)\s+(\w+)(?:\s+UNUSED)?\s*=\s*[^{\"\n]*;", re.M)
MAX_DATA = 16
SOURCES = ROOT / "src"


def data_words(name, data_start, data_end):
    """Word addresses of the overlay's .data variables (DATA_VAR), from its sources; a static's
    address from the ELF's symbols (the map lists only globals), every one of a repeated name."""
    d = SOURCES / ("st" if name.startswith("st") else "boss") / name[2:]
    names = {m[1] for f in sorted(d.glob("*.c")) for m in DATA_VAR.finditer(f.read_text(errors="replace"))
             if "unused" not in m[1].lower() and "pad" not in m[1].lower()}
    out = subprocess.run(["mipsel-linux-gnu-nm", str(BUILD / f"{name}.elf")], capture_output=True, text=True).stdout
    addrs = [int(a, 16) for a, kind, n in (line.split() for line in out.splitlines() if len(line.split()) == 3)
             if n in names and kind in "dDtTbB"]
    words = sorted({a & ~3 for a in addrs if data_start <= a < data_end})
    assert len(words) <= MAX_DATA, (name, len(words))
    return words


def first_word(elf, addr):
    out = subprocess.run(["mipsel-linux-gnu-objdump", "-d", str(elf), f"--start-address={addr:#x}",
                          f"--stop-address={addr + 4:#x}"], capture_output=True, text=True).stdout
    m = re.search(rf"^\s*{addr:x}:\s+([0-9a-f]{{8}})", out, re.M)
    return int(m[1], 16) if m else 0


def main():
    ids = stage_ids()
    rows = []
    for mp in sorted(BUILD.glob("*.map")):
        name = mp.stem
        if name.startswith("st"):
            enum = f"STAGE_{name[2:].upper()}"
        elif name.startswith("bo"):
            enum = f"STAGE_{name[2:].upper()}"
        else:
            continue
        if enum not in ids:
            continue
        text = mp.read_text(errors="replace")
        sym = {m[2]: int(m[1], 16) for m in re.finditer(r"^\s+(0x[0-9a-f]+)\s+(\w+)\s*(?:=.*)?$", text, re.M)}
        bss_start, bss_end = sym.get(f"{name}_BSS_START"), sym.get(f"{name}_BSS_END")
        if bss_start is None or not all(h in sym for h in HELPERS):
            continue
        elf = BUILD / f"{name}.elf"
        helpers = ", ".join(f"{{0x{sym[h]:08X}, 0x{first_word(elf, sym[h]):08X}}}" for h in HELPERS)
        decor = sorted({a for n, a in sym.items() if DECOR.fullmatch(n)})
        assert len(decor) < MAX_DECOR, (name, len(decor))
        decor = "{" + ", ".join(f"0x{a:08X}" for a in decor) + "}"
        cursors = "{" + ", ".join(f"0x{sym.get(c, 0):08X}" for c in CURSORS) + "}"
        text = sym.get("BottomCornerText", 0)
        # ST0's is a different version (the prologue): the module's copy is everyone else's
        solid = sym.get("GetPlayerCollisionWith", 0) if name != "stst0" else 0
        solid = f"{{0x{solid:08X}, 0x{first_word(elf, solid) if solid else 0:08X}}}"
        data = data_words(name, sym.get(f"{name}_DATA_START", 0), sym.get(f"{name}_DATA_END", 0))
        data = "{" + ", ".join(f"0x{a:08X}" for a in data) + "}"
        rows.append(f"    {{{enum}, 0x{bss_start:08X}, 0x{bss_end - bss_start:X}, {{{helpers}}}, {decor}, {cursors}, "
                    f"0x{text:08X}, {solid}, {data}}}, // {name}")
    OUT.write_text("// Generated by scripts/gen_overlay_table.py: do not edit.\n"
                   "// Per stage/boss overlay: BSS range, the targeting helpers to patch, and the scenery\n"
                   "// update functions a shared-room guest runs itself.\n"
                   "#define COOP_MODULE\n#include <game.h>\n#include \"overlay_table.h\"\n\n"
                   "const OverlayInfo g_Overlays[] = {\n" + "\n".join(rows) + "\n    {-1},\n};\n")
    print(f"{len(rows)} overlays -> {OUT.name}")


if __name__ == "__main__":
    main()
