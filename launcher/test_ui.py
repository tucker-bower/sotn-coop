"""The menus in the game's style (launcher/ui), with made-up art and no window: what the font can
draw, how lists move and scroll, and that every screen answers a controller, the keyboard and the
mouse the same. No game data is needed.

    python launcher/test_ui.py
"""

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import pygame  # noqa: E402

from ui import theme as th  # noqa: E402
from ui.screens.castles import castle_list, castle_menu  # noqa: E402
from ui.screens.home import LINKS, home  # noqa: E402
from ui.widgets import Menus, move, scroll  # noqa: E402

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def made_up_art(folder):
    """Plain rectangles in the sizes of the game's art."""
    for name, size in (("font", (128, 128)), ("logo", (119, 63)), ("alucard", (62, 94)), ("richter", (48, 72)),
                       ("maria", (48, 72)), ("icons", (256, 48)), ("switch_on", (48, 16)), ("switch_off", (48, 16))):
        s = pygame.Surface(size, pygame.SRCALPHA)
        s.fill((255, 255, 255, 255))
        pygame.image.save(s, str(Path(folder) / f"{name}.png"))


class Display:
    def __init__(self):
        self.pixels = pygame.Surface((480, 270))
        self.shown = 0

    def present_pixels(self, edge=(0, 0, 0)):
        self.shown += 1


class Inputs:
    """The app's UI, with the frames' actions scripted: one list per frame. A ("mouse", x, y,
    click) is turned into a hover or click on whatever the screen marked there, as app.UI does."""

    def __init__(self, frames):
        self.display, self._rects, self.frames, self.names = Display(), [], list(frames), []

    def seen(self, name):
        if not self.names or self.names[-1] != name:
            self.names.append(name)

    def events(self, pixel=False):
        if not self.frames:
            raise AssertionError("the screen is still waiting after the last scripted input")
        out = []
        for a in self.frames.pop(0):
            if isinstance(a, tuple) and a[0] == "mouse":
                key = next((k for k, r in self._rects if r.collidepoint(a[1], a[2])), None)
                out.append(("click" if a[3] else "hover", key))
            else:
                out.append(a)
        return out


class Sound:
    def __init__(self):
        self.played = []

    def play(self, name):
        self.played.append(name)

    def music(self, on=True):
        self.played.append("music" if on else "music off")


class Castle:
    def __init__(self, name, icon=None, where=None, level=None, rules=""):
        self.name, self._icon, self._rules = name, icon, rules
        self.info = {"name": name, "created": time.time() - 90000, "played": time.time(), "where": where, "level": level}

    def icon(self):
        return self._icon

    def rules_line(self):
        return self._rules


ITEMS = [("solo", "Solo", "Alone"), ("couch", "Couch co-op", "Two here"), ("online", "Online co-op", "Two apart"),
         ("discs", "Discs & mods", ""), ("settings", "Options", ""), ("quit", "Quit", "")]


def main():
    pygame.init()
    # the font: what it draws as itself, what it draws instead, and its own symbols
    check([p for p, _ in th.glyphs("A0 z")] == [0x21, 0x10, 0x00, 0x5A], "a character's place in the font is its code less 0x20")
    check(th.glyphs("{x}{o}") == [(233, False), (232, False)] and th.width("{x} ok") == 32,
          "{x} and {o} are the font's own Cross and Circle, one character wide and never tinted")
    check([p for p, _ in th.glyphs("a_b·c*")] == [p for p, _ in th.glyphs("a b-cx")] and th.glyphs("é")[0][0] == ord("?") - 0x20,
          "what the font hasn't got: a near character where there is one, else a question mark")
    check(th.wrap("one two three four", 9) == ["one two", "three", "four"] and th.shorten("abcdefghij", 6) == "abcd..",
          "text wraps at spaces and shortens with two dots")
    check([move(0, "up", 4), move(3, "down", 4), move(1, "down", 4)] == [3, 0, 2], "a list wraps round at its ends")
    check([scroll(0, 5, 4, 10), scroll(3, 1, 4, 10), scroll(6, 9, 4, 10), scroll(5, 2, 4, 3)] == [2, 1, 6, 0],
          "a list scrolls just enough to show the selected row")

    with tempfile.TemporaryDirectory() as d:
        check(not th.Theme(d).ok, "a folder with no art: the theme says it isn't ready")
        made_up_art(d)
        theme = th.Theme(d)
        check(theme.ok, "with every piece there, it is")

        def menus(frames):
            ui, sound = Inputs(frames), Sound()
            return Menus(ui, theme, sound), ui, sound

        about = lambda key: {"lines": ["Your last castle"], "castle": Castle("Tucker", 3, "Clock Tower", 31), "portrait": "alucard"}  # noqa: E731
        # the main menu, by each device
        m, ui, sound = menus([["down"], ["down"], ["ok"]])
        check(home(m, ITEMS, about, "1.0") == "online" and ui.names == ["Home"], "keyboard or controller: down, down, OK is Online co-op")
        check(sound.played == ["music", "move", "move", "confirm"], f"the title music starts, and each press makes the game's sound: {sound.played}")
        m, ui, _ = menus([[], [("mouse", 40, 86 + 10 + 16 * 1 + 4, False)], [("mouse", 40, 86 + 10 + 16 * 1 + 4, True)]])
        check(home(m, ITEMS, about, "1.0") == "couch", "the mouse: a click on the second row is Couch co-op")
        m, ui, _ = menus([["back"], ["ok"]])
        check(home(m, ITEMS, about, "1.0") == "quit", "back on the main menu goes to Quit, and OK there quits")

        # the links: the mouse only
        m, ui, _ = menus([[], [("mouse", 20, 260, True)]])
        check(home(m, ITEMS, about, "1.0") == ("link", LINKS["github"]), "a click on GitHub opens our GitHub page")
        m, ui, _ = menus([[], [("mouse", 300, 260, True)]])
        check(home(m, ITEMS, about, "1.0") == ("link", LINKS["discord"]) and "discord.gg/q7V9eFtAW" in LINKS["discord"],
              "a click on the Discord line opens our Discord")
        seen = set()
        for presses in range(len(ITEMS) * 2 + 1):
            for way in ("down", "up"):
                m, ui, _ = menus([[way]] * presses + [["ok"]])
                seen.add(home(m, ITEMS, about, "1.0"))
        check(seen == {i[0] for i in ITEMS}, "no number of ups or downs lands on a link: a controller and the keyboard reach the six items only")

        # the castle screen
        last = Castle("Tucker", 3, "Clock Tower", 31)
        m, ui, _ = menus([["ok"]])
        check(castle_menu(m, "Solo", last, True) == "continue", "with a castle, Continue is first and selected")
        m, ui, _ = menus([["ok"]])
        check(castle_menu(m, "Solo", None, False) == "new", "with none, New castle is, and there's no Continue or Load castle")
        m, ui, _ = menus([["down"], ["down"], ["ok"]])
        check(castle_menu(m, "Couch co-op", last, True) == "load" and ui.names == ["Couch co-op"], "then New castle, then Load castle")
        m, ui, _ = menus([["back"]])
        check(castle_menu(m, "Solo", last, True) is None, "back leaves it")

        # the castle list
        castles = [Castle(f"Castle {k}", k % 16, "Marble Gallery", k) for k in range(14)]
        extras = [("tests", "Test castles", "hint"), ("rush", "Boss rush", "hint")]
        m, ui, _ = menus([["down"], ["ok"]])
        check(castle_list(m, "Load castle", castles, extras) == ("castle", castles[1]), "OK plays the selected castle")
        m, ui, _ = menus([["up"], ["ok"]])
        check(castle_list(m, "Load castle", castles, extras) == "rush", "up from the top is the last row: the boss rush")
        m, ui, _ = menus([["down"]] * 13 + [["rules"]])
        check(castle_list(m, "Load castle", castles, extras) == ("rules", castles[13]), "Square / X / S on a castle (scrolled to) opens its settings")
        m, ui, _ = menus([["up"], ["rules"], ["back"]])
        check(castle_list(m, "Load castle", castles, extras) is None, "the boss rush has no settings; back leaves the list")
        m, ui, _ = menus([[], [("mouse", 100, 34 + 8 + 16 * 2 + 4, True)]])
        check(castle_list(m, "Load castle", castles, extras) == ("castle", castles[2]), "the mouse: a click on the third row plays it")

        # a castle's settings
        import rules as castle_rules
        from ui.screens.castle_settings import castle_settings

        def settings(frames, **kw):
            m, ui, _ = menus(frames)
            r, applied = castle_rules.clean({}), []
            got = castle_settings(m, "Tucker", r, applied.append, **kw)
            return got, r, applied, ui

        got, r, applied, ui = settings([["right"], ["back"]])
        check(got is None and castle_rules.difficulty(r) == "Hard" and (r["enemy_hp_pct"], r["taken_pct"], r["exp_pct"]) == (300, 150, 50)
              and applied[-1] == r and ui.names == ["Castle settings"], "Difficulty is the first row: right is Hard, and its sliders move at once")
        got, r, _, _ = settings([["left"], ["left"], ["left"], ["back"]])
        check(castle_rules.difficulty(r) == "Easy", "left stops at Easy")
        got, r, _, _ = settings([["down"], ["right"], ["back"]])
        check(r["enemy_hp_pct"] == 225 and castle_rules.difficulty(r) == "Custom",
              "down skips the group's heading to the first slider; moving it by hand makes the difficulty Custom")
        got, r, _, _ = settings([["down"]] * 6 + [["ok"], ["back"]])
        check(r["shared_level"] is False, "OK on a rule switches it (past the Sharing heading)")
        got, r, applied, _ = settings([["down"]] * 6 + [["ok"], ["up"], ["up"], ["ok"], ["back"]])  # up from the first row: the last, the defaults
        check(got is None and r["shared_level"] is False, "up moves back through the list")
        got, r, applied, _ = settings([["right"], ["up"], ["ok"], ["back"]])
        check(r == castle_rules.clean({}) and applied[-1] == r, "Back to the defaults (the last row) restores every setting")
        got, r, applied, _ = settings([["right"], ["down"], ["right"], ["ok"], ["back"]], read_only=True)
        check(r == castle_rules.clean({}) and applied == [], "the host's settings, shown to a joiner: nothing changes")
        mode = {"mode": "story"}
        got, r, _, _ = settings([["ok"]], start=True, mode=mode)
        check(got == "start" and mode["mode"] == "story", "a new castle: Start is first, and it's a Story castle unless changed")
        got, r, _, _ = settings([["down"], ["right"], ["up"], ["ok"]], start=True, mode=mode)
        check(got == "start" and mode["mode"] == "rush", "Mode is the next row: left or right makes it a Boss rush")
        got, r, _, _ = settings([["down"], ["down"], ["right"], ["back"]], start=True, mode={"mode": "story"})
        check(got is None and castle_rules.difficulty(r) == "Hard", "then Difficulty; back returns to the castle's name")
        got, r, _, _ = settings([["down"], ["right"], ["back"]], start=True)
        check(castle_rules.difficulty(r) == "Hard", "with no boss rush to offer, there's no Mode row")
        got, r, _, _ = settings([["down"]] * 7 + [[], [("mouse", 420, 34 + 6 + 16 * 6 + 4, True)], ["back"]])  # scrolled by two
        check(r["shared_level"] is False and r["shared_gold"] is True, "the mouse: a click on a rule's row switches it")

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
