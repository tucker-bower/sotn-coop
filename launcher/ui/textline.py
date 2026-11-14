"""A line of typed text with a caret, for every box the player types in: a castle's name, a room
code, a bug report's note. Left / Right move the caret, Home / End jump, Backspace / Delete delete
around it (with Ctrl, a word), and a held key repeats as it does in other programs (`typing`)."""

import contextlib

import pygame

REPEAT_DELAY, REPEAT_EVERY = 400, 35  # ms: about what Windows does by default


@contextlib.contextmanager
def typing():
    """Text input on, and held keys repeating, for as long as a box is open (the menus keep their
    own: a held arrow there moves one row)."""
    before = pygame.key.get_repeat()
    pygame.key.set_repeat(REPEAT_DELAY, REPEAT_EVERY)
    pygame.key.start_text_input()
    try:
        yield
    finally:
        pygame.key.stop_text_input()
        pygame.key.set_repeat(*before)


class TextLine:
    def __init__(self, text="", limit=64):
        self.limit = limit
        self.text = text[:limit]
        self.caret = len(self.text)

    def set(self, text):
        """All of it replaced (a pasted room code): the caret at its end."""
        self.text = text[:self.limit]
        self.caret = len(self.text)

    def insert(self, s):
        s = s[:self.limit - len(self.text)]
        self.text = self.text[:self.caret] + s + self.text[self.caret:]
        self.caret += len(s)

    def _word(self, step):
        """Where Ctrl+Left / Ctrl+Right lands: past the spaces, then past the word."""
        i, t = self.caret, self.text
        if step < 0:
            while i > 0 and t[i - 1] == " ":
                i -= 1
            while i > 0 and t[i - 1] != " ":
                i -= 1
        else:
            while i < len(t) and t[i] == " ":
                i += 1
            while i < len(t) and t[i] != " ":
                i += 1
        return i

    def handle(self, ev):
        """Typing and editing keys. True if the event was one (the caller handles the rest)."""
        ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL
        if ev.type == pygame.TEXTINPUT:
            if not ctrl:  # Ctrl+V's "v"
                self.insert(ev.text)
            return True
        if ev.type != pygame.KEYDOWN:
            return False
        ctrl = getattr(ev, "mod", 0) & pygame.KMOD_CTRL
        k = ev.key
        if k == pygame.K_BACKSPACE:
            to = self._word(-1) if ctrl else max(0, self.caret - 1)
            self.text, self.caret = self.text[:to] + self.text[self.caret:], to
        elif k == pygame.K_DELETE:
            to = self._word(1) if ctrl else min(len(self.text), self.caret + 1)
            self.text = self.text[:self.caret] + self.text[to:]
        elif k == pygame.K_LEFT:
            self.caret = self._word(-1) if ctrl else max(0, self.caret - 1)
        elif k == pygame.K_RIGHT:
            self.caret = self._word(1) if ctrl else min(len(self.text), self.caret + 1)
        elif k == pygame.K_HOME:
            self.caret = 0
        elif k == pygame.K_END:
            self.caret = len(self.text)
        else:
            return False
        return True

    def window(self, columns):
        """The part that fits in `columns` characters, keeping the caret in view: (text, caret's
        place in it)."""
        start = max(0, self.caret - columns + 1)
        shown = self.text[start:start + columns]
        return shown, self.caret - start


def blink():
    return pygame.time.get_ticks() // 400 % 2 == 0


def draw_caret(surface, x, y, h, colour):
    """A thin upright bar at x, blinking: between letters, so the text never shifts."""
    if blink():
        pygame.draw.line(surface, colour, (x, y), (x, y + h - 1))
