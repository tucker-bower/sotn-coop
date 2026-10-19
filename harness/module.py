"""Reads the co-op module's symbols (build/coop/coop.map) and its state block in RAM."""

import re
import struct

from coop_env import REPO, TOOLS

COOP_DISC = TOOLS["out"] / "disc/sotn_coop.us.cue"  # scripts/build_disc.sh
COOP_MAGIC = 0x504F4F43  # 'COOP'


def symbols():
    text = (REPO / "build/coop/coop.map").read_text()
    return {m[2]: int(m[1], 16) for m in re.finditer(r"^\s+(0x[0-9a-f]{8})\s+(\w+)$", text, re.M)}


def coop_state(emu):
    """g_Coop from module/coop.c: (magic, version, heartbeat)."""
    return struct.unpack("<III", emu.read_bytes(symbols()["g_Coop"], 12))
