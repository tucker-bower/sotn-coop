"""The game's own art, read from the player's PlayStation disc for the launcher's menus
(design/launcher-overhaul.md): the menu font, the logo, the portraits, the save icons and the
ON / OFF switches. Nothing here ships: it's made on the player's machine, into their data folder.

    python launcher/gameart.py <disc .cue or .bin> <out folder>

    rip(disc, out) -> True if every piece was made (art.json lists them)
    ready(out)     -> True if out holds this version's art

Where each piece is (USA disc; docs/research.md "The game's art and sound"):
- BIN/F_GAME.BIN is 32 sheets of 128x128 4-bit pixels (0x2000 bytes each, 64 bytes a row), then
  the palettes at 0x40000 (16 colours of 2 bytes each; an 8-bit picture uses 16 of them in a row).
- DRA.BIN holds the 16 memory-card save icons: 16 palettes at 0x518, and at 0x718 each icon's
  three 16x16 frames, one above the other.
- Richter's and Maria's 48x72 portraits are in their cutscenes' stages (link/portraits.py).
"""

import json
import mmap
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for sub in ("patcher", ""):
    sys.path.insert(0, str(HERE.parent / sub) if sub else str(HERE.parent))

VERSION = 1  # of what rip() makes: a change here remakes every player's art
SHEET, ROW, PALETTES = 0x2000, 64, 0x40000
FONT = (0x30000, 150)             # 8x8 glyphs, 16 a row: the character's code is its place
LOGO = ((0x2C000, 0x2E000), 208)  # two 64x128 8-bit halves, side by side
ALUCARD = (0x24000, 80)           # 64x128, 8-bit: his pause-menu portrait is the top 96 rows
HUD = (0x38000, 0x97)             # the sheet with the settings' ON and OFF switches
SWITCH_ON, SWITCH_OFF = (0, 112, 48, 16), (48, 112, 48, 16)
ICON_PALETTES, ICONS, ICON_SIZE, ICON_COUNT, ICON_FRAMES = 0x518, 0x718, 0x180, 16, 3
PIECES = ("font", "logo", "alucard", "richter", "maria", "icons", "switch_on", "switch_off")


def colours(data, at, count):
    """count PlayStation colours (5 bits each of red, green, blue) as RGBA; colour 0 is clear."""
    out = []
    for (v,) in struct.iter_unpack("<H", data[at:at + count * 2]):
        out.append((0, 0, 0, 0) if v == 0 else ((v & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v >> 10 & 31) * 255 // 31, 255))
    return out


def picture4(data, at, palette, w, h, row=ROW):
    """A 4-bit picture as RGBA bytes (the low half of each byte is the pixel on the left)."""
    out = bytearray()
    for y in range(h):
        line = data[at + y * row:at + y * row + (w + 1) // 2]
        for x in range(w):
            out += bytes(palette[line[x // 2] >> 4 if x & 1 else line[x // 2] & 15])
    return bytes(out)


def picture8(data, at, palette, w, h, row=None):
    out = bytearray()
    for y in range(h):
        for b in data[at + y * (row or w):at + y * (row or w) + w]:
            out += bytes(palette[b] if b < len(palette) else (0, 0, 0, 0))
    return bytes(out)


def crop(rgba, w, h, box):
    x0, y0, cw, ch = box
    return b"".join(rgba[((y0 + y) * w + x0) * 4:((y0 + y) * w + x0 + cw) * 4] for y in range(ch)), cw, ch


def trim(rgba, w, h):
    """The picture without its clear border."""
    rows = [y for y in range(h) if any(rgba[(y * w + x) * 4 + 3] for x in range(w))]
    cols = [x for x in range(w) if any(rgba[(y * w + x) * 4 + 3] for y in range(h))]
    if not rows:
        return rgba, w, h
    return crop(rgba, w, h, (cols[0], rows[0], cols[-1] - cols[0] + 1, rows[-1] - rows[0] + 1))


def beside(a, b, w, h):
    return b"".join(a[y * w * 4:(y + 1) * w * 4] + b[y * w * 4:(y + 1) * w * 4] for y in range(h))


def pictures(files):
    """{name: (rgba, w, h)} from the disc's files ({path: bytes}); a piece that isn't there is left out."""
    out = {}
    game, dra = files.get("BIN/F_GAME.BIN"), files.get("DRA.BIN")
    if game and len(game) >= PALETTES + 0x2000:
        def pal(n, count=16):
            return colours(game, PALETTES + n * 32, count)
        out["font"] = (picture4(game, FONT[0], pal(FONT[1]), 128, 128), 128, 128)
        halves = [picture8(game, at, pal(LOGO[1], 256), 64, 128) for at in LOGO[0]]
        out["logo"] = trim(beside(halves[0], halves[1], 64, 128), 128, 128)
        out["alucard"] = trim(*crop(picture8(game, ALUCARD[0], pal(ALUCARD[1], 256), 64, 128), 64, 128, (0, 0, 64, 96)))
        hud = picture4(game, HUD[0], pal(HUD[1]), 128, 128)
        out["switch_on"], out["switch_off"] = crop(hud, 128, 128, SWITCH_ON), crop(hud, 128, 128, SWITCH_OFF)
    if dra and len(dra) >= ICONS + ICON_COUNT * ICON_SIZE:
        strips = [picture4(dra, ICONS + n * ICON_SIZE, colours(dra, ICON_PALETTES + n * 32, 16), 16, 16 * ICON_FRAMES, row=8)
                  for n in range(ICON_COUNT)]
        h = 16 * ICON_FRAMES  # one icon a column, its frames down it
        out["icons"] = (b"".join(b"".join(s[y * 64:(y + 1) * 64] for s in strips) for y in range(h)), 16 * ICON_COUNT, h)
    from link import portraits
    for name, (path, pixels, palette) in zip(("richter", "maria"), portraits.PARTS):
        stage = files.get(path)
        if stage and len(stage) >= max(pixels + portraits.PIXELS, palette + portraits.PALETTE):
            out[name] = (picture8(stage, pixels, colours(stage, palette, 128), 48, 72), 48, 72)
    return out


def disc_files(disc, paths):
    """{path: bytes} of files on a disc image (.cue or its data track); a missing one is left out."""
    from link import portraits
    from patcher import find_file
    out = {}
    with open(portraits.track(disc), "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as image:
        for path in paths:
            place = find_file(image, path)
            if place:
                out[path] = portraits._span(image, place[0], 0, place[1])
    return out


def psp_icon(iso, out):
    """The PSP game's own icon (PSP_GAME/ICON0.PNG, 144x80), from the player's disc image, for the
    discs screen. True if it's there."""
    import characters
    try:
        disc = characters.Iso(iso)
        try:
            data = disc.read("PSP_GAME/ICON0.PNG")
        finally:
            disc.close()
    except Exception:  # noqa: BLE001 - no icon: the slot shows the characters it unlocked
        return False
    if not data or not data.startswith(b"\x89PNG"):
        return False
    Path(out).write_bytes(data)
    return True


def ready(out):
    try:
        about = json.loads((Path(out) / "art.json").read_text())
    except (OSError, ValueError):
        return False
    return about.get("version") == VERSION and all((Path(out) / f"{p}.png").exists() for p in about.get("pieces", ()))


def rip(disc, out):
    """Makes the art in out (a folder in the player's data). Returns True if every piece was made."""
    import pygame
    from link import portraits
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        files = disc_files(disc, ["BIN/F_GAME.BIN", "DRA.BIN"] + [p[0] for p in portraits.PARTS])
    except (OSError, ValueError, TypeError, AttributeError):
        files = {}
    made = pictures(files)
    for name, (rgba, w, h) in made.items():
        pygame.image.save(pygame.image.frombuffer(rgba, (w, h), "RGBA"), str(out / f"{name}.png"))
    (out / "art.json").write_text(json.dumps({"version": VERSION, "pieces": sorted(made)}))
    return all(p in made for p in PIECES)


if __name__ == "__main__":
    print("all made" if rip(sys.argv[1], sys.argv[2]) else "some pieces are missing")
