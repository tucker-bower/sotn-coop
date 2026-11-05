"""The crash watch and the window after it (issue 113): what counts as stopped, and that nothing
is sent unless the player says so."""

import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

import crash_window  # noqa: E402
import crashwatch  # noqa: E402
from link.mailbox import BUSY, IN_PLAY  # noqa: E402

failed = []


def check(ok, what):
    print(("ok  " if ok else "FAIL"), what)
    if not ok:
        failed.append(what)


class Game:
    name = "A"

    def __init__(self):
        self.vector, self.frame, self.beat, self.flags = bytes(16), 1, 1, IN_PLAY

    def read_bytes(self, where, size):
        return self.vector

    def mailbox(self, name):
        return self.beat if name == "heartbeat" else NS(frame=self.frame, flags=self.flags)


def watched(step, seconds):
    """Checks once a second, step(game) between. Returns the first problem."""
    g, w = Game(), crashwatch.CrashWatch()
    for _ in range(seconds):
        why = w.check([g])
        if why:
            return why
        step(g)
    return None


def ticks(g):
    g.frame += 60
    g.beat += 60


def in_a_menu(g):  # the pause and equip menus: the game's timer stops, its main loop runs
    g.beat += 60


check(watched(ticks, 60) is None, "a game that's running is left alone")
check("hung" in (watched(lambda g: None, 30) or ""), "a timer stopped in play is a hang")
check(watched(lambda g: None, 9) is None, "not within nine seconds")
check(watched(in_a_menu, 60) is None, "a minute in the pause menu isn't a hang (issues 150, 152)")


def not_in_play(g):
    g.flags = BUSY


check(watched(not_in_play, 60) is None, "a stopped timer out of play isn't (the ending's movie, a load)")


def overwrite(g):
    g.vector = bytes(15) + b"\x01"


check("crashed" in (watched(overwrite, 3) or ""), "an overwritten vector is a crash")

path = Path(tempfile.mkdtemp()) / "report.zip"
path.write_bytes(b"report")


def window(*events, can=True):
    """Runs the window with these events; returns (its result, the calls to send)."""
    with mock.patch.object(crash_window.report, "can_send", return_value=can), \
         mock.patch.object(crash_window.report, "send", return_value=None) as send, \
         mock.patch.object(pygame.event, "get", side_effect=[list(events)] + [[]] * 100):
        return crash_window.run(path), send


KEY = lambda key: pygame.event.Event(pygame.KEYDOWN, key=key)  # noqa: E731
result, send = window(pygame.event.Event(pygame.QUIT))
check(result == "kept" and not send.called, "closing the window sends nothing")
result, send = window(KEY(pygame.K_ESCAPE))
check(result == "kept" and not send.called, "Esc sends nothing")
result, send = window(KEY(pygame.K_RETURN), can=False)
check(result == "kept" and not send.called, "with no way to send, nothing is sent")
result, send = window(pygame.event.Event(pygame.TEXTINPUT, text="froze"), KEY(pygame.K_RETURN))
check(result == "sent" and send.call_count == 1 and send.call_args[0] == (path, "froze"),
      "Enter sends it once, with the note")

print("all passed" if not failed else f"{len(failed)} FAILED")
sys.exit(1 if failed else 0)
