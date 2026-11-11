"""The menus' look: the game's own (design/launcher-overhaul.md). Text is drawn in the game's
menu font, windows as the pause menu draws them (a blue gradient with a white border; the cursor
is a red bar that pulses), all on the display's pixel canvas, in the game's pixels.

The art is the player's own, read from their disc by gameart.py into their data folder: a Theme
is made from that folder, and `ok` says whether everything it needs is there.
"""

from pathlib import Path

import pygame

GLYPH = 8
INK, DIM, GOLD, GREEN, RED = (255, 255, 255), (150, 152, 184), (248, 208, 112), (136, 224, 136), (255, 120, 120)
BACK = (0, 0, 8)                       # behind the windows
WINDOW_TOP, WINDOW_BOTTOM = (0, 0, 32), (32, 32, 96)  # the pause menu's default window colours
# What the game's font can draw as itself (its other places hold Japanese)
DRAWN = set(" !\"#$%&'()+,-./0123456789:=?ABCDEFGHIJKLMNOPQRSTUVWXYZ[]abcdefghijklmnopqrstuvwxyz")
INSTEAD = {"_": " ", "·": "-", "—": "-", "–": "-", "›": "-", ">": "-", "<": "-", "*": "x", ";": ",", "’": "'", "‘": "'",
           "“": '"', "”": '"', "…": ".", "@": "a", "|": "/", "\\": "/", "~": "-", "×": "x", "{": "(", "}": ")"}
# The font's own symbols, written in text as {x}, {o}, {s}, {t} and the arrows {<}, {^}, {>}, {v}:
# they keep their own colours.
SYMBOLS = {"<": 224, "^": 226, ">": 228, "v": 230, "o": 232, "x": 233, "s": 234, "t": 235}
NEEDS = ("font", "logo", "alucard", "richter", "maria", "icons", "switch_on", "switch_off")


def glyphs(text):
    """text as the font's places: [(place in the sheet, tinted?)]. {x} and the like are symbols."""
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "{" and i + 2 < len(text) and text[i + 2] == "}" and text[i + 1] in SYMBOLS:
            out.append((SYMBOLS[text[i + 1]], False))
            i += 3
            continue
        c = c if c in DRAWN else INSTEAD.get(c, "?")
        out.append((ord(c) - 0x20, True))
        i += 1
    return out


def width(text):
    return len(glyphs(text)) * GLYPH


def wrap(text, columns):
    """text's lines, broken at spaces to fit that many characters."""
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = f"{line} {word}" if line else word
            if line and len(glyphs(trial)) > columns:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return out


def shorten(text, columns):
    return text if len(glyphs(text)) <= columns else text[:max(0, columns - 2)].rstrip() + ".."


class Theme:
    def __init__(self, folder):
        self.pictures = {}
        for name in NEEDS:
            try:
                self.pictures[name] = pygame.image.load(str(Path(folder) / f"{name}.png"))
            except (pygame.error, OSError, FileNotFoundError):
                pass
        self.ok = all(n in self.pictures for n in NEEDS)
        self._tinted = {}

    def _font(self, colour):
        sheet = self._tinted.get(colour)
        if sheet is None:
            sheet = self.pictures["font"].copy()
            sheet.fill((*colour, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._tinted[colour] = sheet
        return sheet

    def text(self, surface, text, x, y, colour=INK):
        """Draws one line; returns the x after it."""
        tinted, plain = self._font(colour), self.pictures["font"]
        for place, tint in glyphs(text):
            surface.blit(tinted if tint else plain, (x, y), (place % 16 * GLYPH, place // 16 * GLYPH, GLYPH, GLYPH))
            x += GLYPH
        return x

    def text_right(self, surface, text, right, y, colour=INK):
        self.text(surface, text, right - width(text), y, colour)

    def text_centre(self, surface, text, centre, y, colour=INK):
        self.text(surface, text, centre - width(text) // 2, y, colour)

    def window(self, surface, rect):
        """A window as the pause menu draws one."""
        rect = pygame.Rect(rect)
        for k in range(rect.h):
            f = k / max(1, rect.h - 1)
            c = [round(a + (b - a) * f) for a, b in zip(WINDOW_TOP, WINDOW_BOTTOM)]
            pygame.draw.line(surface, c, (rect.x, rect.y + k), (rect.right - 1, rect.y + k))
        pygame.draw.rect(surface, INK, rect, 1)

    def cursor(self, surface, rect, ticks=None):
        """The red bar behind the selected row: its red goes 0x60..0x7F and back every 64 frames."""
        frame = (pygame.time.get_ticks() if ticks is None else ticks) * 60 // 1000
        step = frame & 0x1F
        red = 0x60 + step if frame & 0x20 else 0x7F - step
        pygame.draw.rect(surface, (red * 2 - 0x40, 0, 0), rect)

    def picture(self, surface, name, x, y, scale=1):
        p = self.pictures[name]
        if scale != 1:
            p = pygame.transform.scale(p, (p.get_width() * scale, p.get_height() * scale))
        surface.blit(p, (x, y))
        return p.get_size()

    def icon(self, surface, number, x, y, moving=True, scale=1, ticks=None):
        """A save's icon (0..15): its three frames, a third of a second each, as the file select
        shows them. Not moving: its first frame."""
        frame = ((pygame.time.get_ticks() if ticks is None else ticks) // 333) % 3 if moving else 0
        cell = self.pictures["icons"].subsurface((number % 16 * 16, frame * 16, 16, 16))
        if scale != 1:
            cell = pygame.transform.scale(cell, (16 * scale, 16 * scale))
        surface.blit(cell, (x, y))

    def switch(self, surface, on, x, y):
        surface.blit(self.pictures["switch_on" if on else "switch_off"], (x, y))
