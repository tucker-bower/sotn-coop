"""A line of text in the game's style: a castle's name, a room code. Typed (the on-screen keyboard
on a phone), or pasted: Ctrl+V, or Square / X on a controller (A in an empty box pastes too).
Left / Right move the caret, and held keys repeat (ui/textline.py)."""

import pygame

from ..textline import TextLine, draw_caret, typing
from ..theme import DIM, GOLD, INK, shorten

BOX = (40, 60, 400, 120)


def text_entry(m, heading, about, initial="", paste=None, limit=64, pad="", keys=""):
    """Returns the text (stripped), or None (back)."""
    t, s, line = m.theme, m.s, TextLine(initial, limit)
    with typing():
        while True:
            for a in m.poll(raw=True, quiet=("up", "down", "left", "right", "ok")):  # (Space is "ok": a letter here)
                if not (isinstance(a, tuple) and a[0] == "event"):
                    continue
                ev = a[1]
                if line.handle(ev):
                    continue
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        return line.text.strip()
                    if ev.key in (pygame.K_ESCAPE, pygame.K_AC_BACK):
                        return None
                    if ev.key == pygame.K_v and (ev.mod & pygame.KMOD_CTRL) and paste:
                        line.set(paste() or line.text)
                elif ev.type == pygame.CONTROLLERBUTTONDOWN:
                    if ev.button == pygame.CONTROLLER_BUTTON_B:
                        return None
                    if ev.button == pygame.CONTROLLER_BUTTON_X and paste:
                        line.set(paste() or line.text)
                    elif ev.button in (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_START):
                        if not line.text and paste and paste():
                            line.set(paste())
                        else:
                            return line.text.strip()
            m.begin(heading, about)
            m.window(BOX)
            x = BOX[0] + 12
            t.text(s, shorten(heading, 46), x, BOX[1] + 10, GOLD)
            t.paragraph(s, about, x, BOX[1] + 26, 46, 3, DIM)
            field = pygame.Rect(x, BOX[1] + 66, BOX[2] - 24, 18)
            pygame.draw.rect(s, (0, 0, 16), field)
            pygame.draw.rect(s, INK, field, 1)
            shown, at = line.window((field.w - 12) // 8)
            t.text(s, shown, field.x + 5, field.y + 5, INK)
            draw_caret(s, field.x + 4 + 8 * at, field.y + 3, 12, INK)
            m.footer(pad or "{x} done   {o} back", keys or "Type   Enter: done   Esc: back")
            m.show()
