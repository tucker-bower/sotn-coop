"""The game's art for the menus (launcher/gameart.py), on made-up files: no game data is needed, and
none is made. With a dev checkout's disc (COOP_TEST_DISC, or disks/sotn.us.cue) it also rips the
real one into a temporary folder and checks every piece.

    python launcher/test_gameart.py
"""

import os
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import gameart  # noqa: E402

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def px(picture, x, y):
    rgba, w, _ = picture
    return tuple(rgba[(y * w + x) * 4:(y * w + x) * 4 + 4])


def made_up_game():
    """A file shaped like BIN/F_GAME.BIN: one white dot per piece, where each piece is read from."""
    game = bytearray(gameart.PALETTES + 0x2000)

    def palette(n, index, colour=0x7FFF):
        struct.pack_into("<H", game, gameart.PALETTES + n * 32 + index * 2, colour)
    palette(gameart.FONT[1], 1)
    game[gameart.FONT[0] + 8 * gameart.ROW + 4] = 0x10  # the pixel at (9, 8): the high half is the right one
    palette(gameart.LOGO[1], 200, 0x001F)  # red, colour 200 of 256
    game[gameart.LOGO[0][0] + 10 * 64 + 60] = 200
    game[gameart.LOGO[0][1] + 20 * 64 + 5] = 200  # the right half: x = 64 + 5
    palette(gameart.ALUCARD[1], 3)
    for x, y in ((0, 0), (63, 95), (10, 120)):  # the last is under the portrait: not his
        game[gameart.ALUCARD[0] + y * 64 + x] = 3
    palette(gameart.HUD[1], 2)
    game[gameart.HUD[0] + 112 * gameart.ROW] = 0x02      # the ON switch's first pixel
    game[gameart.HUD[0] + 112 * gameart.ROW + 24] = 0x02  # the OFF switch's
    return bytes(game)


def made_up_dra():
    dra = bytearray(gameart.ICONS + gameart.ICON_COUNT * gameart.ICON_SIZE)
    for n in range(gameart.ICON_COUNT):
        struct.pack_into("<H", dra, gameart.ICON_PALETTES + n * 32 + 2, 0x03E0)  # colour 1: green
        dra[gameart.ICONS + n * gameart.ICON_SIZE + (16 * 2 + n) * 8] = 0x01  # frame 2, row n, first pixel
    return bytes(dra)


def main():
    check(gameart.colours(struct.pack("<3H", 0, 0x7FFF, 0x001F), 0, 3) == [(0, 0, 0, 0), (255, 255, 255, 255), (255, 0, 0, 255)],
          "a PlayStation colour: 0 is clear, the rest are solid, red is the low five bits")

    made = gameart.pictures({"BIN/F_GAME.BIN": made_up_game(), "DRA.BIN": made_up_dra()})
    check(set(made) == {"font", "logo", "alucard", "icons", "switch_on", "switch_off"},
          f"the pieces of the files that are there are made, the others left out: {sorted(made)}")
    font = made["font"]
    check(font[1:] == (128, 128) and px(font, 9, 8) == (255, 255, 255, 255) and px(font, 8, 8)[3] == 0,
          "the font is the 128x128 sheet, and a byte's high half is the pixel on the right")
    logo = made["logo"]
    check(logo[1:] == (10, 11) and px(logo, 0, 0) == (255, 0, 0, 255) and px(logo, 9, 10) == (255, 0, 0, 255),
          f"the logo is its two halves side by side, without the clear border: {logo[1:]}")
    check(made["alucard"][1:] == (64, 96), f"Alucard's portrait is the top 96 rows: {made['alucard'][1:]}")
    check(made["switch_on"][1:] == (48, 16) and px(made["switch_on"], 0, 0)[3] == 255 and px(made["switch_off"], 0, 0)[3] == 255,
          "the ON and OFF switches are cut from their sheet")
    icons = made["icons"]
    check(icons[1:] == (256, 48) and all(px(icons, n * 16, 32 + n) == (0, 255, 0, 255) for n in range(16)),
          "the save icons: one a column, three frames down, each in its own palette")

    check(gameart.pictures({}) == {} and gameart.pictures({"BIN/F_GAME.BIN": b"short", "DRA.BIN": b""}) == {},
          "no files, or files too short to hold the art: nothing is made, nothing raises")

    with tempfile.TemporaryDirectory() as d:
        check(not gameart.ready(d), "an empty folder isn't ready")
        ok = gameart.rip(Path(d) / "no-such-disc.cue", Path(d) / "art")
        check(ok is False and not gameart.ready(Path(d) / "missing") and gameart.ready(Path(d) / "art"),
              "a disc that can't be read: rip says pieces are missing, and isn't asked again for this version")

    disc = os.environ.get("COOP_TEST_DISC") or HERE.parent / "disks" / "sotn.us.cue"
    if Path(disc).exists():
        import pygame
        with tempfile.TemporaryDirectory() as d:  # (game data: gone when the test ends)
            check(gameart.rip(disc, d) and gameart.ready(d), "the real disc: every piece is made")
            sizes = {p: pygame.image.load(str(Path(d) / f"{p}.png")).get_size() for p in gameart.PIECES}
            check(sizes["font"] == (128, 128) and sizes["icons"] == (256, 48) and sizes["richter"] == sizes["maria"] == (48, 72)
                  and sizes["alucard"][1] >= 90 and sizes["logo"][0] > 100, f"the real disc: the pieces' sizes {sizes}")
    else:
        print("     (no disc here: the real rip isn't checked)")

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
