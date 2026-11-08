"""Playable characters beyond Alucard (design/M8): Maria, from the player's own Dracula X
Chronicles (USA) disc image.

    maria_blob(iso, patches, out) -> path     builds data/characters/maria.blob once: Co-op Maria's
                                              blob, then Ultimate Maria's (docs/design/character-mods.md)
    blob_bytes(character) -> bytes or None    what a game's 8MB RAM gets (module/link.h CharBlob)

Our Richter needs nothing here: he's on the co-op disc (COOPRIC.BIN). Maria's overlay and voice
are rebuilt from the player's DXC files with patches of our changes only (characters/maria-dx/make_patches.py):
nothing of hers is distributed.
"""

import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patcher"))
import bps  # noqa: E402

CHAR_ALUCARD, CHAR_RICHTER, CHAR_MARIA, CHAR_ULT_MARIA, CHAR_SAT_MARIA = 0, 1, 2, 3, 4   # module/link.h
BLOBS_MAX = 0x180000  # module/link.h: CHAR_BLOB_ADDR to CHAR_BLOBS_END
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
    def part(name):
        try:
            return bps.apply(files[about["patches"][name]["source"]], (patches / name).read_bytes())
        except bps.PatchError as e:
            raise DiscError(f"That disc image doesn't match the one Maria was made for ({e}).") from e

    def one(character, ovl, vh, vb, partner):
        pad = lambda b: b + bytes(-len(b) % 4)  # noqa: E731
        # then her partner build (design/M13 step 3: module/link.h CharBlob.partnerSize)
        head = struct.pack("<8I", CHAR_BLOB_MAGIC, character, len(ovl), len(vh), len(vb), len(partner), 0, 0)
        return head + pad(ovl) + pad(vh) + pad(vb) + pad(partner)

    vh, vb = part("maria-vh.bps"), part("maria-vb.bps")
    blob = one(CHAR_MARIA, part("maria.bps"), vh, vb, part("maria-partner.bps"))
    if "ult-maria.bps" in about["patches"]:  # Ultimate Maria: her own code, Co-op Maria's voice
        blob += one(CHAR_ULT_MARIA, part("ult-maria.bps"), vh, vb, part("ult-maria-partner.bps"))
    blob += bytes(4)  # the end of the blobs (module/link.h CHAR_BLOB_NEXT)
    assert len(blob) <= BLOBS_MAX, len(blob)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    return out


# --- Saturn Maria (docs/design/character-mods.md): SOTN Ultimate's, from the player's Saturn disc

SATURN_GAME = "Akumajou Dracula X: Gekka no Yasoukyoku (Japan) (2M)"  # the Redump name, Track 1


class RawDisc(Iso):
    """A raw CD image's track 1 (2352-byte sectors): the Saturn's (mode 1) or the PlayStation's
    (mode 2, form 1)."""

    def __init__(self, path):
        self.f = open(path, "rb")
        self.f.seek(16 * 2352 + 15)
        mode = self.f.read(1)
        self.skip = 16 if mode == b"\x01" else 24
        pvd = self._sector(16)
        if pvd[1:6] != b"CD001":
            self.f.close()
            raise DiscError("That file isn't a CD image's data track (.bin). Choose the .cue of your rip.")
        self.root = pvd[156:156 + 34]

    def _sector(self, n, count=1):
        out = []
        for k in range(count):
            self.f.seek((n + k) * 2352 + self.skip)
            out.append(self.f.read(SECTOR))
        return b"".join(out)


def track1(path):
    """Track 1 of a .cue (or a .bin itself)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "patcher"))
    import patcher
    try:
        return patcher.find_track1(path)[0]
    except patcher.DiscError as e:
        raise DiscError(str(e)) from e


def saturn_files(disc, about):
    """The Saturn files Saturn Maria is made from, checked against the disc she was made for."""
    d = RawDisc(track1(disc))
    try:
        files = {name: d.read(name) for name in about["saturn_files"]}
    finally:
        d.close()
    if not files["MARIA.PRG"]:
        raise DiscError("That isn't the Saturn Symphony of the Night: Saturn Maria comes from "
                        f"{SATURN_GAME}.")
    bad = [n for n, b in files.items() if not b or hashlib.md5(b).hexdigest() != about["saturn_files"][n]]
    if bad:
        raise DiscError("That's the Saturn game, but not the copy Saturn Maria was made for (a translation "
                        f"or another version?). She needs the original Japanese disc: {SATURN_GAME}, from "
                        "redump.org.")
    return files


def saturn_maria_blob(saturn_disc, coop_disc, patches, out):
    """Builds Saturn Maria's blob from the player's Saturn disc and their co-op disc (Richter's art
    she keeps: RIC.BIN, which the co-op disc has as retail did); returns out. Raises DiscError."""
    import saturn_maria
    patches = Path(patches)
    about = json.loads((patches / "sat-maria.json").read_text())
    files = saturn_files(saturn_disc, about)
    ps1 = RawDisc(track1(coop_disc))
    try:
        ric = ps1.read(about["source"])
    finally:
        ps1.close()
    if not ric:
        raise DiscError("Your co-op disc has no Richter (BIN/RIC.BIN). Make it again in Settings › Game files.")
    try:
        ovl = bytearray(bps.apply(ric, (patches / "sat-maria.bps").read_bytes()))
        partner = bytearray(bps.apply(ric, (patches / "sat-maria-partner.bps").read_bytes()))
    except bps.PatchError as e:
        raise DiscError(f"Your co-op disc's Richter isn't the one Saturn Maria was made for ({e}).") from e
    made = saturn_maria.arrays(files.__getitem__, lambda p: ric)  # read_ps1: only BIN/RIC.BIN
    for name, (at, size, digest) in about["arrays"].items():
        data = made.get(name)
        if data is None or len(data) != size or hashlib.md5(data).hexdigest() != digest:
            raise DiscError(f"Saturn Maria's {name} didn't come out as it should. Please send us a bug report (F9).")
        ovl[at:at + size] = data
        p = about["partner_arrays"][name]
        partner[p:p + size] = data
    pad = lambda b: bytes(b) + bytes(-len(b) % 4)  # noqa: E731
    # her overlay, no sound bank of her own yet (Richter's), then her partner build
    blob = struct.pack("<8I", CHAR_BLOB_MAGIC, CHAR_SAT_MARIA, len(ovl), 0, 0, len(partner), 0, 0)
    blob += pad(ovl) + pad(partner)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)  # one blob, no end mark: blobs() joins it to the others
    return out


def blobs(*parts):
    """The blobs for a game's 8MB RAM, one after another, from their files' bytes (each one blob,
    or maria.blob's two with its end mark), then the end mark (module/link.h CHAR_BLOB_NEXT)."""
    out = b""
    for p in parts:
        if p:
            out += p[:-4] if p[-4:] == bytes(4) and len(p) % 4 == 0 and _ends_marked(p) else p
    out += bytes(4)
    assert len(out) <= BLOBS_MAX, len(out)
    return out


def _ends_marked(p):
    """Whether p is blobs ending with the end mark (walks the headers)."""
    at = 0
    while at + 32 <= len(p) and struct.unpack_from("<I", p, at)[0] == CHAR_BLOB_MAGIC:
        sizes = struct.unpack_from("<4I", p, at + 8)
        at += 32 + sum((n + 3) & ~3 for n in sizes)
    return at == len(p) - 4
