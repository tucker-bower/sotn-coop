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
        words = []
        for word in para.split(" "):  # (a word too long for a line, a folder's path: broken where it must be)
            while len(glyphs(word)) > columns > 0:
                words.append(word[:columns])
                word = word[columns:]
            words.append(word)
        for word in words:
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


def plain_font():
    """A stand-in for the game's font, from a system one: the same 8x8 places, the letters only.
    Each letter is drawn large, cut to the band every letter's ink fits in (tails too), and that
    band is shrunk to 8 pixels: whatever the font's own spacing, nothing is cut off."""
    sheet = pygame.Surface((128, 128), pygame.SRCALPHA)
    pygame.font.init()
    font = pygame.font.SysFont("consolas,dejavusansmono,liberationmono,couriernew,monospace", 16)
    letters = {code - 0x20: chr(code) for code in range(0x21, 0x7F)}
    letters.update({224: "<", 226: "^", 228: ">", 230: "v", 232: "O", 233: "X", 234: "#", 235: "A"})  # the symbols, as letters
    drawn = {place: font.render(letter, True, (255, 255, 255)) for place, letter in letters.items()}
    inked = [g.get_bounding_rect() for g in drawn.values() if g.get_bounding_rect().h]
    top, bottom = min(r.top for r in inked), max(r.bottom for r in inked)
    band = bottom - top
    for place, glyph in drawn.items():
        ink = glyph.get_bounding_rect()
        if not ink.w:
            continue
        cut = glyph.subsurface((ink.x, top, ink.w, band))
        w = max(1, min(GLYPH, round(ink.w * GLYPH / band)))
        small = pygame.transform.smoothscale(cut.convert_alpha() if pygame.display.get_surface() else cut, (w, GLYPH))
        sheet.blit(small, (place % 16 * GLYPH + (GLYPH - w) // 2, place // 16 * GLYPH))
    return sheet


class Theme:
    def __init__(self, folder):
        self.pictures = {}
        for name in NEEDS:
            try:
                self.pictures[name] = pygame.image.load(str(Path(folder) / f"{name}.png"))
            except (pygame.error, OSError, FileNotFoundError):
                pass
        self.ok = all(n in self.pictures for n in NEEDS)
        self.folder = Path(folder)
        self.load_sprites()
        if "font" not in self.pictures:  # before the player's disc is attached: plain letters, same size
            self.pictures["font"] = plain_font()
        self._tinted = {}

    def load_sprites(self):
        """The characters standing (launcher/sprites.py), as many as the player's discs have given,
        and the hand-drawn "co-op" (Tucker's, launcher/assets/coop-scrawl.png) if it's there."""
        for p in self.folder.glob("sprite-*.png"):
            try:
                self.pictures[p.stem] = pygame.image.load(str(p))
            except (pygame.error, OSError):
                pass
        scrawl = Path(__file__).resolve().parent.parent / "assets" / "coop-scrawl.png"
        if scrawl.exists() and "scrawl" not in self.pictures:
            try:
                self.pictures["scrawl"] = pygame.image.load(str(scrawl))
            except (pygame.error, OSError):
                pass

    def _font(self, colour):
        sheet = self._tinted.get(colour)
        if sheet is None:
            sheet = self.pictures["font"].copy()
            sheet.fill((*colour, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._tinted[colour] = sheet
        return sheet

    def frame(self):
        """A new frame: the windows drawn in it, and any text that ran out of its window."""
        self.windows, self.overflows = [], []

    def _fits(self, surface, text, x, y, end):
        """Text must end inside the window it starts in (or the screen): else it's cut off. Tests read
        self.overflows (launcher/test_ui.py), so a screen that cuts text off fails, not just looks wrong."""
        box = next((w for w in reversed(getattr(self, "windows", [])) if w.collidepoint(x, y)), surface.get_rect())
        inside = box.right if box == surface.get_rect() else box.right - 1  # (a window's last column is its border)
        if end > inside or x < box.left or y + GLYPH > box.bottom:
            self.overflows = getattr(self, "overflows", [])
            self.overflows.append((text, x, y, tuple(box)))

    def text(self, surface, text, x, y, colour=INK):
        """Draws one line; returns the x after it."""
        self._fits(surface, text, x, y, x + width(text))
        tinted, plain = self._font(colour), self.pictures["font"]
        for place, tint in glyphs(text):
            surface.blit(tinted if tint else plain, (x, y), (place % 16 * GLYPH, place // 16 * GLYPH, GLYPH, GLYPH))
            x += GLYPH
        return x

    def paragraph(self, surface, text, x, y, columns, lines, colour=INK, step=10):
        """Wrapped text, at most `lines` lines. Text that needs more is cut off: noted, as text past
        its window is, so a test fails on it (launcher/test_screens_fit.py)."""
        parts = wrap(text, columns)
        if len(parts) > lines:
            self.overflows = getattr(self, "overflows", [])
            self.overflows.append((text, x, y, ("needs", len(parts), "lines; has", lines)))
        for k, line in enumerate(parts[:lines]):
            self.text(surface, line, x, y + k * step, colour)
        return min(len(parts), lines)

    def text_right(self, surface, text, right, y, colour=INK):
        self.text(surface, text, right - width(text), y, colour)

    def text_centre(self, surface, text, centre, y, colour=INK):
        self.text(surface, text, centre - width(text) // 2, y, colour)

    def text_big(self, surface, text, centre, y, colour=INK, scale=2):
        """One line at a whole multiple of the font's size (a room code), centred on centre."""
        line = pygame.Surface((width(text), GLYPH), pygame.SRCALPHA)
        self.text(line, text, 0, 0, colour)
        line = pygame.transform.scale(line, (line.get_width() * scale, GLYPH * scale))
        surface.blit(line, (centre - line.get_width() // 2, y))

    def window(self, surface, rect):
        """A window as the pause menu draws one."""
        rect = pygame.Rect(rect)
        self.windows = getattr(self, "windows", []) + [rect]
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
