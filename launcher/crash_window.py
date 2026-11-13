"""The bug report window after a crash or hang (issue 113): its own process, so a stuck game can't
take it down. The report is already saved. Nothing is sent unless the player says so here: closing
the window sends nothing.

    app --crash-window REPORT.zip"""

import sys
import threading
from pathlib import Path

import pygame

import report
from ui.textline import TextLine, draw_caret, typing

SIZE = (640, 360)
BACKGROUND, TEXT, DIM, BOX = (16, 12, 20), (230, 230, 230), (160, 160, 170), (40, 34, 50)
SENT = ("Your note, screenshots, inputs, logs, game state and memory cards go",
        "to the SOTN Co-op team by email. Your folders, disc path, typed name",
        "and IP address are removed.")


class Choice:
    """The window's state: the note, and what the player chose."""

    def __init__(self):
        self.line, self.send = TextLine("", 500), False
        self.done = False

    @property
    def note(self):
        return self.line.text

    def handle(self, ev):
        if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
            self.done = True
        elif self.line.handle(ev):
            pass
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.done = True
        elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.send = self.done = True


def draw(screen, font, path, choice, lines):
    screen.fill(BACKGROUND)
    y = 16
    for text, colour in lines:
        screen.blit(font.render(text, True, colour), (16, y))
        y += font.get_linesize() + 4
    pygame.draw.rect(screen, BOX, (16, y + 4, SIZE[0] - 32, 28))
    shown, at = choice.line.window(70)
    screen.blit(font.render(shown, True, TEXT), (22, y + 8))
    draw_caret(screen, 22 + font.size(shown[:at])[0], y + 7, font.get_height() + 2, TEXT)
    pygame.display.flip()


def run(path):
    """Shows the window until the player chooses. Returns what happened, for tests."""
    path = Path(path)
    pygame.init()
    screen = pygame.display.set_mode(SIZE)
    pygame.display.set_caption("SOTN Co-op: the game stopped")
    font = pygame.font.Font(None, 22)
    can = report.can_send()
    lines = [("The game stopped. A bug report is saved:", TEXT), (str(path)[-76:], DIM), ("", DIM)]
    if can:
        lines += [(t, DIM) for t in SENT]
        lines += [("Enter: send it.   Esc or closing this window: keep it here, nothing is sent.", TEXT)]
    else:
        lines += [(f"Please email it to {report.REPORT_EMAIL}.   Esc: close.", TEXT)]
    lines += [("What were you doing? (optional)", DIM)]
    choice = Choice()
    clock = pygame.time.Clock()
    with typing():
        while not choice.done:
            for ev in pygame.event.get():
                choice.handle(ev)
            draw(screen, font, path, choice, lines)
            clock.tick(30)
    if not (choice.send and can):
        pygame.quit()
        return "kept"
    result = {}
    worker = threading.Thread(target=lambda: result.update(error=report.send(path, choice.note)), daemon=True)
    worker.start()
    lines[-2:] = [("Sending...", TEXT)]
    while worker.is_alive():
        pygame.event.pump()
        draw(screen, font, path, choice, lines)
        clock.tick(30)
    pygame.quit()
    return result.get("error") or "sent"


if __name__ == "__main__":
    run(sys.argv[1])
