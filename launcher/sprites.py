"""The characters standing, as the game draws them, for the main menu's title (issue 232): each read
from the player's own discs, the moment the disc that has them is attached, into the data folder's
art/ (sprite-<name>.png). Nothing of the game ships.

    ps1(disc, out)          Alucard and Richter, from the PlayStation disc
    psp(iso, out)           Maria, from the Dracula X Chronicles disc
    saturn(disc, blob, out) Maria and Richter (Saturn): her from the Saturn disc, him from his coat blob

Where they are (docs/research.md "The characters' sprites"):
- A sprite sheet is a table of pointers to frames: width, height, pivot x, pivot y, then 4-bit
  pixels (the low nibble is the left pixel). Frame 0 is standing.
- Alucard's frames are built from parts as he plays; the Doppelganger's stage (BOSS/BO4/BO4.BIN,
  table 0x435C at 0x80180000) has the same body as whole frames. Alucard's own palette is
  F_GAME.BIN's first (palette 0x100, at 0x40000).
- Richter: BIN/RIC.BIN, table 0x20 at 0x8013C000; his palette 0x120 is F_GAME2.BIN's at 0x40400.
- Maria (PSP): PSP_GAME/USRDIR/res/ps/PSPBIN/maria.bin, loaded at 0x09228A00; her table ends where
  her sheet does (0x2D560), and her palette is at 0x14B18.
- Richter (Saturn): his blob (characters.py) is RIC.BIN in the coat, after a 32-byte header; the
  coat's palettes are in the block "RIC2" points to, palette 0x120 among them.
- Maria (Saturn): MARIA.PRG / MARIA.CHR on the Saturn disc, through saturn_maria.MariaSaturn.
"""

import struct
from pathlib import Path

NAMES = ("alucard", "richter", "maria", "maria-saturn", "richter-saturn")  # = the lobby's characters' order


def colours(data, at, count=16):
    return [(0, 0, 0, 0) if v & 0x7FFF == 0 else ((v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31, 255)
            for (v,) in struct.iter_unpack("<H", data[at:at + count * 2])]


def frame(data, table, base, index=0):
    """(w, h, 4-bit pixels) of a sheet's frame, or None."""
    try:
        p = struct.unpack_from("<I", data, table + 4 * index)[0] - base
        w, h = data[p], data[p + 1]
    except (struct.error, IndexError):
        return None
    if not w or not h or w * h > 128 * 128:
        return None
    return w, h, data[p + 4:p + 4 + (w * h + 1) // 2]


def rgba(f, palette):
    """RGBA bytes of a frame: colour 0 is always clear (the Saturn's is a real colour, unused)."""
    w, h, px = f
    palette = [(0, 0, 0, 0)] + list(palette[1:])
    out = bytearray()
    for k in range(w * h):
        v = px[k // 2]
        out += bytes(palette[(v >> 4) if k & 1 else (v & 15)])
    return bytes(out), w, h


def save(picture, path):
    import pygame
    data, w, h = picture
    pygame.image.save(pygame.image.frombuffer(data, (w, h), "RGBA"), str(path))


def ps1(disc, out):
    """Alucard's and Richter's, from the PlayStation disc. Returns the names made."""
    import gameart
    files = gameart.disc_files(disc, ["BIN/F_GAME.BIN", "BIN/F_GAME2.BIN", "BIN/RIC.BIN", "BOSS/BO4/BO4.BIN"])
    made = []
    game, bo4 = files.get("BIN/F_GAME.BIN"), files.get("BOSS/BO4/BO4.BIN")
    f = frame(bo4, 0x435C, 0x80180000) if bo4 else None
    if f and game:
        save(rgba(f, colours(game, 0x40000)), Path(out) / "sprite-alucard.png")
        made.append("alucard")
    ric, g2 = files.get("BIN/RIC.BIN"), files.get("BIN/F_GAME2.BIN")
    f = frame(ric, 0x20, 0x8013C000) if ric else None
    if f and g2:
        save(rgba(f, colours(g2, 0x40400)), Path(out) / "sprite-richter.png")
        made.append("richter")
    return made


def psp(iso, out):
    """Maria's, from the Dracula X Chronicles disc. True if made."""
    import characters
    try:
        disc = characters.Iso(iso)
        try:
            m = disc.read("PSP_GAME/USRDIR/res/ps/PSPBIN/maria.bin")
        finally:
            disc.close()
    except Exception:  # noqa: BLE001 - no picture: the title has the others
        return False
    base, start, end = 0x09228A00, 0x1D750, 0x2D560
    if not m or len(m) < end:
        return False
    at = end  # (the PSP's tables come after their frames: back from the sheet's end)
    while at - 4 > start and start <= struct.unpack_from("<I", m, at - 4)[0] - base < end:
        at -= 4
    f = frame(m, at, base)
    if not f:
        return False
    save(rgba(f, colours(m, 0x14B18)), Path(out) / "sprite-maria.png")
    return True


def saturn(disc, blob, out, about=None):
    """Maria's and Richter's (Saturn): her from the Saturn disc, him from his coat blob. Returns the
    names made."""
    made = []
    try:
        b = Path(blob).read_bytes()[32:]
        f = frame(b, 0x20, 0x8013C000)
        mark = b.find(b"RIC2")
        if f and mark > 0:
            at = struct.unpack_from("<I", b, mark + 4)[0] - 0x8013C000
            n = struct.unpack_from("<I", b, at)[0]
            for k in range(n):
                which = struct.unpack_from("<I", b, at + 4 + k * 36)[0]
                if which == 0x120:
                    save(rgba(f, colours(b, at + 8 + k * 36)), Path(out) / "sprite-richter-saturn.png")
                    made.append("richter-saturn")
                    break
    except (OSError, struct.error, IndexError):
        pass
    try:
        import characters
        import saturn_maria
        files = characters.saturn_files(disc, about) if about else None
        if files:
            s = saturn_maria.MariaSaturn(files["MARIA.PRG"], files["MARIA.CHR"])
            first = next(fr for fr in s.frames() if fr)
            img = s.image(first[3])
            palette = [(0, 0, 0, 0) if v & 0x7FFF == 0 else ((v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31, 255)
                       for v in s.palette(0)]
            palette[0] = (0, 0, 0, 0)
            data = b"".join(bytes(palette[v]) for v in img.px)
            save((data, img.w, img.h), Path(out) / "sprite-maria-saturn.png")
            made.append("maria-saturn")
    except Exception:  # noqa: BLE001 - no picture: the title has the others
        pass
    return made
