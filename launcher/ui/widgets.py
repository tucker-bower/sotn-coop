"""What the screens in the game's style are made of: one loop of input and drawing (Menus), and
the list every menu is. A screen is a function that draws with these and returns what was chosen.

Input is the app's own (app.UI.events): up, down, left, right, ok, back from a controller or the
keyboard, and the mouse as ("hover", key) and ("click", key) on whatever a screen marked with
hit(). So every screen works with all three.
"""

import pygame

from .theme import BACK, DIM, GLYPH, GOLD, INK, shorten, width

ROW = 16  # a menu row's height


class Menus:
    def __init__(self, ui, theme, sound):
        self.ui, self.theme, self.sound = ui, theme, sound
        self.s = ui.display.pixels
        self.device = "keys"  # what was last used: the footer shows its buttons
        self.name = ""

    # --- one frame

    def begin(self, name):
        """A new frame of the screen called name (what tests and bug reports know it by)."""
        self.name = name
        self.ui.seen(name)
        self.s.fill(BACK)
        self.ui._rects = []

    def hit(self, key, rect):
        """Marks rect as something the mouse can point at and click."""
        self.ui._rects.append((key, pygame.Rect(rect)))

    def show(self):
        self.ui.display.present_pixels(BACK)
        pygame.time.wait(16)

    def poll(self, quiet=()):
        """This frame's actions. Plays the game's sound for each, but not for those in quiet."""
        out = []
        for a in self.ui.events(pixel=True):
            if a == "quit":
                raise SystemExit
            if isinstance(a, tuple) and a[0] == "pad":
                self.device = "pad"
                continue
            if isinstance(a, tuple) and a[0] == "device":
                self.device = a[1]
                continue
            name = {"up": "move", "down": "move", "left": "move", "right": "move", "ok": "confirm", "back": "back"}.get(a)
            if isinstance(a, tuple) and a[0] == "click":
                name = "confirm"
            if name and a not in quiet and self.sound:
                self.sound.play(name)
            out.append(a)
        return out

    # --- pieces

    def window(self, rect, title=None):
        self.theme.window(self.s, rect)
        if title:
            self.theme.text(self.s, title, rect[0] + 8, rect[1] + 6, GOLD)

    def rows(self, rect, rows, sel, first=0, key=None, draw=None):
        """A list in a window's inside (rect): the cursor behind row `sel`, each row hit-marked
        as (key, index) or just its index. rows: labels, or anything draw(row, x, y, selected)
        draws. Returns how many rows fit."""
        x, y, w, h = rect
        fits = max(1, h // ROW)
        for k in range(first, min(len(rows), first + fits)):
            top = y + (k - first) * ROW
            if k == sel:
                self.theme.cursor(self.s, (x, top, w, ROW - 2))
            if draw:
                draw(rows[k], x + 6, top + 3, k == sel)
            else:
                self.theme.text(self.s, shorten(rows[k], (w - 12) // GLYPH), x + 6, top + 3, INK)
            self.hit(k if key is None else (key, k), (x, top, w, ROW))
        if first:
            self.theme.text(self.s, "{^}", x + w - 10, y - 2)
        if first + fits < len(rows):
            self.theme.text(self.s, "{v}", x + w - 10, y + h - 8)
        return fits

    def footer(self, pad, keys, right=""):
        """The controls, for whichever of the controller and keyboard was last used."""
        self.theme.text(self.s, pad if self.device == "pad" else keys, 8, 244, DIM)
        if right:
            self.theme.text_right(self.s, right, 472, 244, DIM)

    def link(self, key, text, x, y, hover, right=False):
        """Text only the mouse can use: never part of a controller's or the keyboard's way round."""
        if right:
            x -= width(text)
        on = hover == key
        self.theme.text(self.s, text, x, y, INK if on else DIM)
        if on:
            pygame.draw.line(self.s, INK, (x, y + GLYPH), (x + width(text) - 1, y + GLYPH))
        self.hit(key, (x - 2, y - 2, width(text) + 4, GLYPH + 5))


def move(sel, action, count):
    """sel after an up or down in a list of count."""
    if action == "up":
        return (sel - 1) % count
    if action == "down":
        return (sel + 1) % count
    return sel


def scroll(first, sel, fits, count):
    """The first row shown, so that sel is."""
    if sel < first:
        return sel
    if sel >= first + fits:
        return sel - fits + 1
    return max(0, min(first, count - fits))
