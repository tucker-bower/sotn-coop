"""Streamer mode (#327): no room code, connect code or IP address is ever drawn on the screen.

A room code is the key to the room's ntfy.sh topic, where each game posts its addresses, and to
the room itself. With the setting on, every text the launcher draws goes through hide(): the
game-style menus (ui/theme.py), the older menus (app.UI), the pause menu (gameview.py). The code
is still copied to the clipboard, and the pause menu offers to copy it again.

    streamer.on = True; streamer.hide("Rejoin BAT-7K2Q") == "Rejoin (hidden)"
"""

import re

from link.rendezvous import _FIND

on = False
HIDDEN = "(hidden)"
_MORE = (
    re.compile(r"(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])"),            # an IPv4 address alone
    re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{1,4}:){1,7}:(?:[0-9A-Fa-f]{1,4}(?::[0-9A-Fa-f]{1,4})*)?(?![0-9A-Fa-f:])"),  # IPv6, with ::
    re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}(?![0-9A-Fa-f:])"),  # IPv6
)
drawn = None  # tests: a set that collects every text as drawn (launcher/test_streamer.py, uxdriver)


def hide(text):
    """text with any room code, connect code or IP address in it replaced by "(hidden)",
    while streamer mode is on."""
    if on and text:
        for pattern in (_FIND[0], _FIND[2], *_MORE, *_rooms()):
            text = pattern.sub(HIDDEN, text)
    if drawn is not None and text:
        drawn.add(text)
    return text


def typed(text):
    """What a text box shows of what was typed: dots, while streamer mode is on."""
    return "." * len(text) if on and text else text


_ROOMS = []


def _rooms():
    """A room code in any case: with its dash (BAT-7K2Q), or without one when it has a digit
    (bat7k2q), so words like "Catches" stay as they are."""
    if not _ROOMS:
        from link.rendezvous import ALPHABET, ROOM_WORDS
        words, ch = "|".join(ROOM_WORDS), f"[{ALPHABET}{ALPHABET.lower()}]"
        _ROOMS.append(re.compile(rf"(?i)(?<![A-Z0-9])(?:{words})-{ch}{{4}}(?![A-Z0-9])"))
        _ROOMS.append(re.compile(rf"(?i)(?<![A-Z0-9])(?:{words})(?=[A-Z]{{0,3}}[2-9])[A-Z0-9]{{4}}(?![A-Z0-9])"))
    return _ROOMS
