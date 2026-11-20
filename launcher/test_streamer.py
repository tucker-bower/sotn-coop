"""Streamer mode (#327): what launcher/streamer.py hides, and that the menus' text goes through it.

    python launcher/test_streamer.py
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import streamer  # noqa: E402

fails = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


streamer.on = False
check(streamer.hide("Rejoin BAT-7K2Q") == "Rejoin BAT-7K2Q", "off: nothing hidden")
streamer.on = True
for text, want in (("Rejoin BAT-7K2Q", "Rejoin (hidden)"), ("Hosting room ORB-9XZP, on UDP port 47811.", "Hosting room (hidden), on UDP port 47811."),
                   ("Room code: bat-7k2q", "Room code: (hidden)"), ("joining bat7k2q", "joining (hidden)"),
                   ("192.168.1.10:54321", "(hidden)"), ("ip 203.0.113.9 now", "ip (hidden) now"),
                   ("2601:1c2:b00:3deb::1 or 2601:1c2:b00:3deb:f06d:c696:2337:acf1", "(hidden) or (hidden)"),
                   ("Ping 4:59 left, best 1:02.33", "Ping 4:59 left, best 1:02.33"),
                   ("K7M2-9P4Q-W3", "(hidden)"), ("Catches the bats", "Catches the bats"), ("Impulse", "Impulse"),
                   ("Castle settings", "Castle settings"), ("Version 1.3.0", "Version 1.3.0")):
    got = streamer.hide(text)
    check(got == want if want is not None else "2337" not in got, f"{text!r} -> {got!r}")
check(streamer.typed("BAT-7K2Q") == "........", "a code box shows dots")

import pygame  # noqa: E402
pygame.init()
from ui import theme as th  # noqa: E402
t = th.Theme(str(HERE / "no-art-here"))
surface = pygame.Surface((480, 270))
streamer.drawn = set()
t.text_centre(surface, "Rejoin BAT-7K2Q", 240, 10)
check(streamer.drawn == {"Rejoin (hidden)"}, f"the game-style menus draw it hidden: {streamer.drawn}")
import app  # noqa: E402
streamer.drawn = set()
app._hide("Hosting room BAT-7K2Q, on UDP port 47811.")
check(streamer.drawn == {"Hosting room (hidden), on UDP port 47811."}, "the older menus too (Help › About)")
print(f"\n{'all passed' if not fails else f'{len(fails)} FAILED'}")
sys.exit(1 if fails else 0)
