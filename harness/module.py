"""Reads the co-op module's symbols (build/coop/coop.map) and its state block in RAM."""

import os
import re
import struct
from pathlib import Path

from coop_env import REPO, TOOLS

# scripts/build_disc.sh's, or COOP_DISC=<.cue> (e.g. the disc the patcher made: M6 criterion 7)
COOP_DISC = Path(os.environ["COOP_DISC"]) if os.environ.get("COOP_DISC") else TOOLS["out"] / "disc/sotn_coop.us.cue"
COOP_MAGIC = 0x504F4F43  # 'COOP'


def symbols(disc=None):
    """The module's symbols for that disc (default COOP_DISC): build_disc.sh keeps the map next
    to each disc it builds, so a newer build elsewhere can't shift them. Else the build's map."""
    own = Path(str(disc or COOP_DISC)).with_suffix(".coop.map")
    text = (own if own.exists() else REPO / "build/coop/coop.map").read_text()
    return {m[2]: int(m[1], 16) for m in re.finditer(r"^\s+(0x[0-9a-f]{8})\s+(\w+)$", text, re.M)}


def stage_symbol(overlay, name):
    """A symbol's address in a stage or boss overlay of the us build (e.g. "stno3")."""
    text = (REPO / f"build/us/{overlay}.map").read_text()
    m = re.search(rf"^\s+(0x[0-9a-f]{{8}})\s+{name}$", text, re.M)
    return int(m[1], 16)


def coop_state(emu):
    """The g_CoopLink header (module/link.h): (magic, version, heartbeat)."""
    return struct.unpack("<III", emu.read_bytes(symbols()["g_CoopLink"], 12))


def maria_blob():
    """Maria's CharBlob for tests (launcher/characters.py), built once from the dev DXC disc
    (disks/sotn.pspus.iso) and maria/make_patches.py's patches; None if they aren't there."""
    out = TOOLS["out"] / "maria"
    blob = out / "maria.blob"
    iso = REPO / "disks/sotn.pspus.iso"
    if not blob.exists() or (out / "maria.bps").stat().st_mtime > blob.stat().st_mtime:
        if not (out / "maria.bps").exists() or not iso.exists():
            return None
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
        import characters
        characters.maria_blob(iso, out, blob)
    return blob.read_bytes()
