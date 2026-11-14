"""Typing in a box (a castle's name, a room code, a bug report's note): the caret moves with
Left / Right, Backspace and Delete work around it, and a held key repeats (ui/textline.py).

    python launcher/test_textline.py
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import pygame  # noqa: E402

from ui import theme as th  # noqa: E402
from ui.textline import REPEAT_DELAY, REPEAT_EVERY, TextLine, typing  # noqa: E402
from ui.widgets import Menus  # noqa: E402

failures = []


def check(ok, what):
    print(("ok  " if ok else "FAIL"), what)
    if not ok:
        failures.append(what)


def key(k, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=k, mod=mod, unicode="")


def typed(s):
    return pygame.event.Event(pygame.TEXTINPUT, text=s)


def main():
    pygame.init()
    line = TextLine("Tucker")
    check(line.caret == 6, "the caret starts at the end")
    for ev in (key(pygame.K_LEFT), key(pygame.K_LEFT), typed("X")):
        line.handle(ev)
    check(line.text == "TuckXer" and line.caret == 5, f"Left twice, then a letter goes in there: {line.text!r}")
    line.handle(key(pygame.K_BACKSPACE))
    check(line.text == "Tucker" and line.caret == 4, "Backspace deletes before the caret")
    line.handle(key(pygame.K_DELETE))
    check(line.text == "Tuckr" and line.caret == 4, "Delete deletes after it")
    line.handle(key(pygame.K_HOME))
    line.handle(key(pygame.K_LEFT))
    check(line.caret == 0, "Home goes to the start, and Left stops there")
    line.handle(key(pygame.K_END))
    line.handle(key(pygame.K_RIGHT))
    check(line.caret == 5, "End goes to the end, and Right stops there")
    for _ in range(20):  # a held Backspace: its repeats
        line.handle(key(pygame.K_BACKSPACE))
    check(line.text == "" and line.caret == 0, "Backspace held past the start empties it, no error")

    line = TextLine("the bat carry")
    line.handle(key(pygame.K_BACKSPACE, pygame.KMOD_LCTRL))
    check(line.text == "the bat ", f"Ctrl+Backspace deletes a word: {line.text!r}")
    line.handle(key(pygame.K_LEFT, pygame.KMOD_LCTRL))
    check(line.caret == 4, "Ctrl+Left goes back a word")

    line = TextLine("abc", limit=5)
    line.handle(key(pygame.K_HOME))
    line.handle(typed("12345"))
    check(line.text == "12abc" and line.caret == 2, f"the limit holds when typing mid-line: {line.text!r}")

    line = TextLine("a" * 30 + "b" * 30)
    shown, at = line.window(20)
    check(len(shown) <= 20 and shown.endswith("b") and at == len(shown), "a long line shows its end, caret last")
    line.handle(key(pygame.K_HOME))
    shown, at = line.window(20)
    check(shown.startswith("a") and at == 0, "Home scrolls it back to the start")

    pygame.key.set_repeat(0, 0)
    with typing():
        check(pygame.key.get_repeat() == (REPEAT_DELAY, REPEAT_EVERY), "while typing, held keys repeat")
    check(pygame.key.get_repeat() == (0, 0), "and after, the menus' own setting is back")

    # the real box: typed, edited, Enter
    import test_ui
    from ui.screens.text_entry import text_entry
    with tempfile.TemporaryDirectory() as d:
        test_ui.made_up_art(d)
        ev = lambda e: ("event", e)  # noqa: E731
        ui = test_ui.Inputs([[ev(typed("Tuker"))], [ev(key(pygame.K_LEFT)), "left"], [ev(key(pygame.K_LEFT)), "left"], [ev(key(pygame.K_LEFT))],
                             [ev(typed("c"))], [ev(key(pygame.K_END)), ev(typed("!"))], [ev(key(pygame.K_RETURN)), "ok"]])
        sound = test_ui.Sound()
        got = text_entry(Menus(ui, th.Theme(d), sound), "Name your castle", "Any name")
        check(got == "Tucker!", f"the castle name box: typed, a letter put in the middle, Enter: {got!r}")
        check("move" not in sound.played and "confirm" not in sound.played,
              f"moving the caret (and Space) make no menu sounds: {sound.played}")

    print("all passed" if not failures else f"{len(failures)} FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
