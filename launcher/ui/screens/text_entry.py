"""A line of text in the game's style: a castle's name, a room code. Typed (the on-screen keyboard
on a phone), or pasted: Ctrl+V, or Square / X on a controller (A in an empty box pastes too)."""

import pygame

from ..theme import DIM, GOLD, INK, shorten

BOX = (40, 60, 400, 120)


def text_entry(m, heading, about, initial="", paste=None, limit=64, pad="", keys=""):
    """Returns the text (stripped), or None (back)."""
    t, s, text = m.theme, m.s, initial
    pygame.key.start_text_input()
    try:
        while True:
            for a in m.poll(raw=True):
                if not (isinstance(a, tuple) and a[0] == "event"):
                    continue
                ev = a[1]
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        return text.strip()
                    if ev.key in (pygame.K_ESCAPE, pygame.K_AC_BACK):
                        return None
                    if ev.key == pygame.K_BACKSPACE:
                        text = text[:-1]
                    elif ev.key == pygame.K_v and (ev.mod & pygame.KMOD_CTRL) and paste:
                        text = (paste() or text)[:limit]
                elif ev.type == pygame.TEXTINPUT and len(text) < limit and not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    text += ev.text[:limit - len(text)]
                elif ev.type == pygame.CONTROLLERBUTTONDOWN:
                    if ev.button == pygame.CONTROLLER_BUTTON_B:
                        return None
                    if ev.button == pygame.CONTROLLER_BUTTON_X and paste:
                        text = (paste() or text)[:limit]
                    elif ev.button in (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_START):
                        if not text and paste and paste():
                            text = paste()[:limit]
                        else:
                            return text.strip()
            m.begin(heading, about)
            m.window(BOX)
            x = BOX[0] + 12
            t.text(s, shorten(heading, 46), x, BOX[1] + 10, GOLD)
            t.paragraph(s, about, x, BOX[1] + 26, 46, 3, DIM)
            field = pygame.Rect(x, BOX[1] + 66, BOX[2] - 24, 18)
            pygame.draw.rect(s, (0, 0, 16), field)
            pygame.draw.rect(s, INK, field, 1)
            cursor = "_" if pygame.time.get_ticks() // 400 % 2 else " "
            shown = text[-((field.w - 12) // 8 - 1):] + cursor
            t.text(s, shown, field.x + 5, field.y + 5, INK)
            m.footer(pad or "{x} done   {o} back", keys or "Type   Enter: done   Esc: back")
            m.show()
    finally:
        pygame.key.stop_text_input()
