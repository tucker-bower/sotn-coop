"""Playable characters beyond Alucard (design/M8): Maria, from the player's own Dracula X
Chronicles (USA) disc image.

    maria_blob(iso, patches, out) -> path     builds data/characters/maria.blob once
    blob_bytes(character) -> bytes or None    what a game's 8MB RAM gets (module/link.h CharBlob)

Our Richter needs nothing here: he's on the co-op disc (COOPRIC.BIN). Maria's overlay and voice
are rebuilt from the player's DXC files with patches of our changes only (maria/make_patches.py):
nothing of hers is distributed.
"""

import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patcher"))
import bps  # noqa: E402

CHAR_ALUCARD, CHAR_RICHTER, CHAR_MARIA = 0, 1, 2   # module/link.h
CHAR_BLOB_MAGIC = 0x52414843                       # 'CHAR'
SECTOR = 2048
DXC_USA = "ULUS-10277"
DXC_OTHERS = {  # game id -> what to tell the player
    "ULES-00841": "That's the European PSP version (ULES-00841). Maria needs the USA one (ULUS-10277).",
    "ULJM-05201": "That's the Japanese PSP version (ULJM-05201). Maria needs the USA one (ULUS-10277).",
}
FILES = {"maria.bin": "PSP_GAME/USRDIR/res/ps/PSPBIN/maria.bin",
         "sd_mar2.spk": "PSP_GAME/USRDIR/res/ps/snd_e/SE/sd_mar2.spk"}


class DiscError(Exception):
    """Something the player should be told, in plain words."""


class Iso:
    """Just enough ISO 9660 to read files from a PSP disc image (2048-byte sectors)."""

    def __init__(self, path):
        self.f = open(path, "rb")
        pvd = self._sector(16)
        if pvd[1:6] != b"CD001":
            self.f.seek(16 * 2352 + 25)  # a raw CD image (2352-byte sectors): a PlayStation disc
            if self.f.read(5) == b"CD001":
                raise DiscError("That's a PlayStation disc. Maria comes from the PSP game: choose your "
                                "Dracula X Chronicles .iso (USA, ULUS-10277).")
            raise DiscError("That file isn't a disc image (.iso). Choose your Dracula X Chronicles .iso.")
        self.root = pvd[156:156 + 34]

    def _sector(self, n, count=1):
        self.f.seek(n * SECTOR)
        return self.f.read(SECTOR * count)

    def _entries(self, record):
        lba, size = struct.unpack_from("<I", record, 2)[0], struct.unpack_from("<I", record, 10)[0]
        data = self._sector(lba, (size + SECTOR - 1) // SECTOR)
        pos = 0
        while pos < size:
            n = data[pos]
            if n == 0:  # entries don't cross sectors: skip to the next one
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            entry = data[pos:pos + n]
            name = entry[33:33 + entry[32]].decode("ascii", "replace").split(";")[0]
            yield name, entry
            pos += n

    def read(self, path):
        record = self.root
        for part in path.split("/"):
            for name, entry in self._entries(record):
                if name.upper() == part.upper():
                    record = entry
                    break
            else:
                return None
        lba, size = struct.unpack_from("<I", record, 2)[0], struct.unpack_from("<I", record, 10)[0]
        return self._sector(lba, (size + SECTOR - 1) // SECTOR)[:size]

    def close(self):
        self.f.close()


def check_dxc(iso_path):
    """Raises DiscError unless it's the USA Dracula X Chronicles."""
    iso = Iso(iso_path)
    try:
        umd = iso.read("UMD_DATA.BIN") or b""
        game = umd.split(b"|")[0].decode("ascii", "replace")
        if game in DXC_OTHERS:
            raise DiscError(DXC_OTHERS[game])
        if game != DXC_USA:
            raise DiscError("That isn't Castlevania: The Dracula X Chronicles (PSP, USA, ULUS-10277).")
    finally:
        iso.close()


def maria_blob(iso_path, patches, out):
    """Builds Maria's blob from the DXC disc and our patches; returns out. Raises DiscError."""
    check_dxc(iso_path)
    patches = Path(patches)
    about = json.loads((patches / "maria.json").read_text())
    iso = Iso(iso_path)
    try:
        files = {name: iso.read(path) for name, path in FILES.items()}
    finally:
        iso.close()
    if not all(files.values()):
        raise DiscError("Maria's files aren't on that disc image. Is it a complete copy?")
    parts = []
    for name in ("maria.bps", "maria-vh.bps", "maria-vb.bps", "maria-partner.bps"):
        try:
            parts.append(bps.apply(files[about["patches"][name]["source"]], (patches / name).read_bytes()))
        except bps.PatchError as e:
            raise DiscError(f"That disc image doesn't match the one Maria was made for ({e}).") from e
    ovl, vh, vb, partner = parts
    pad = lambda b: b + bytes(-len(b) % 4)  # noqa: E731
    # then her partner build (design/M13 step 3: module/link.h CharBlob.partnerSize)
    blob = struct.pack("<8I", CHAR_BLOB_MAGIC, CHAR_MARIA, len(ovl), len(vh), len(vb), len(partner), 0, 0)
    blob += pad(ovl) + pad(vh) + pad(vb) + partner
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    return out
