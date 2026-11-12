"""The menus in the game's style (launcher/ui), with made-up art and no window: what the font can
draw, how lists move and scroll, and that every screen answers a controller, the keyboard and the
mouse the same. No game data is needed.

    python launcher/test_ui.py
"""

import collections
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

    def seen(self, name, about=""):
        self.about = about
        if not self.names or self.names[-1] != name:
            self.names.append(name)

    def events(self, raw=False, pixel=False):
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
        m, ui, _ = menus([["up"], ["up"], ["ok"]])
        check(castle_menu(m, "Solo", last, True, has_tests=True) == "tests", "Test castles is a button of its own, before Back")
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
        got, r, _, _ = settings([["down"], ["down"], ["right"], ["back"]])
        check(r["enemy_hp_pct"] == 225 and castle_rules.difficulty(r) == "Custom",
              "Balance is the first page: Difficulty, Back to the defaults, the sliders; moving one by hand makes it Custom")
        got, r, _, _ = settings([["page_next"], ["ok"], ["back"]])
        check(r["shared_level"] is False, "R1 / E: the Sharing page; OK on its first rule switches it")
        got, r, _, _ = settings([["page_next"], ["right"], ["back"]])
        off = r["shared_level"]
        got, r, _, _ = settings([["page_next"], ["right"], ["left"], ["back"]])
        check(off is False and r["shared_level"] is True, "a switch: right turns it OFF, left turns it ON, as it's drawn")
        got, r, _, _ = settings([["page_prev"], ["ok"], ["back"]])
        check(r["bat_carry"] is not castle_rules.clean({})["bat_carry"], "L1 / Q from the first page: the last page, Extras")
        got, r, _, _ = settings([["page_next"]] * 7 + [["down"], ["down"], ["right"], ["back"]])
        check(r["enemy_hp_pct"] == 225, "the pages go round: seven on, Balance again")
        got, r, applied, _ = settings([["right"], ["down"], ["ok"], ["back"]])
        check(r == castle_rules.clean({}) and applied[-1] == r, "Back to the defaults (under Difficulty) restores every setting")
        got, r, applied, _ = settings([["page_next"], ["ok"], ["page_prev"], ["down"], ["ok"], ["back"]])
        check(got is None and r == castle_rules.clean({}), "...from any page's change")
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
        got, r, _, _ = settings([["page_next"], [], [("mouse", 420, 34 + 6 + 4, True)], ["back"]])
        check(r["shared_level"] is False and r["shared_gold"] is True, "the mouse: a click on a rule's row switches it")

        # pages in a list of options (issue 253)
        from ui.screens.options import options
        orows = [{"kind": "head", "key": None, "label": "One"}, {"kind": "switch", "key": "a", "label": "A", "value": False},
                 {"kind": "action", "key": "b", "label": "B"}, {"kind": "head", "key": None, "label": "Two"},
                 {"kind": "action", "key": "c", "label": "C"}]
        m, ui, _ = menus([["page_next"], ["ok"]])
        check(options(m, lambda: orows, lambda *a: None, pages=True) == ("c", 4), "Options: R1 / E turns to the next page")
        m, ui, _ = menus([["down"], ["ok"]])
        check(options(m, lambda: orows, lambda *a: None, pages=True) == ("b", 2), "up and down stay on the page")
        m, ui, _ = menus([["page_prev"], ["down"], ["ok"]])
        check(options(m, lambda: orows, lambda *a: None, pages=True) == ("c", 4), "L1 / Q goes round to the last page")

        # each player's buttons (issue 250)
        import gameview
        check(gameview.bind({}, "cross", "b", gameview.DEFAULT_PAD) == {"cross": "b", "circle": "a"},
              "a button given to Cross swaps with the one that had it")
        check(gameview.bind({"cross": "b", "circle": "a"}, "cross", "a", gameview.DEFAULT_PAD) == {},
              "setting it back to the default leaves nothing stored")

        class Pad:
            def __init__(self, down=(), axes=()):
                self.down, self.axes = down, axes

            def get_button(self, b):
                return b in self.down

            def get_axis(self, a):
                return 30000 if a in self.axes else 0
        pads = gameview.Pads.__new__(gameview.Pads)
        pads.assign, pads.virtual, pads.controllers = [7, None], {}, []
        pads.by_id = {7: Pad({pygame.CONTROLLER_BUTTON_B})}
        pads.pad_maps, pads.key_maps = [gameview.pad_map(), gameview.pad_map()], [dict(gameview.KEYS[0]), dict(gameview.KEYS[1])]
        nokeys = collections.defaultdict(bool)
        check(pads.mask(0, nokeys) == "circle", "the controller's right face button is Circle by default")
        pads.set_buttons(0, {"cross": "b", "circle": "a"}, {"cross": "q"})
        check(pads.mask(0, nokeys) == "cross", "rebound: it's Cross for that player")
        pads.by_id = {7: Pad()}
        keys = collections.defaultdict(bool, {pygame.K_q: True})
        check(pads.mask(0, keys) == "cross" and pads.mask(1, keys) == "l1", "a key rebound for player 1 only; player 2 keeps Q as L1")
        keys = collections.defaultdict(bool, {pygame.K_z: True})
        check("cross" not in pads.mask(0, keys).split("+"), "the old key no longer presses it")
        pads.by_id = {7: Pad(axes={pygame.CONTROLLER_AXIS_TRIGGERLEFT})}
        pads.set_buttons(0, gameview.bind({}, "square", "lefttrigger", gameview.DEFAULT_PAD), {})
        check(pads.mask(0, nokeys) == "square", "a trigger can be any button (and L2 gets Square's old one)")

        # your discs
        from ui.screens.discs import discs

        def disc_screen(frames, first_run=False, have=None):
            m, ui, _ = menus(frames)
            have = dict(have or {})
            calls = []

            def attach(slot, path):
                calls.append((slot, path))
                where = slot or ("psp" if str(path).endswith(".iso") else "ps1")
                have[where] = path or f"{where}.bin"
                return where, f"{where} attached", True
            got = discs(m, lambda: dict(have), attach, first_run, more=("Randomizer", "BIOS"))
            return got, calls, have, ui

        got, calls, _, ui = disc_screen([["down"], ["ok"], ["right"], ["ok"]], first_run=True)
        check(got == "quit" and calls == [] and "PlayStation" in ui.about,
              "first run: Continue does nothing without the PlayStation disc (and says why); Quit quits")
        got, calls, _, _ = disc_screen([["back"], ["down"], ["right"], ["ok"]], first_run=True)
        check(got == "quit", "first run: back doesn't leave")
        got, calls, have, _ = disc_screen([["ok"], ["ok"]], first_run=True)
        check(calls == [("ps1", None)] and got == "continue", "first run: OK on the PlayStation slot browses for it; once it's there, Continue is selected")
        drop = pygame.event.Event(pygame.DROPFILE, file="/somewhere/dxc.iso")
        got, calls, have, _ = disc_screen([[("event", drop)], ["back"]], have={"ps1": "sotn.cue"})
        check(calls == [(None, "/somewhere/dxc.iso")] and have.get("psp") and got == "back",
              "a file dropped anywhere goes to attach with no slot (it's sorted by what's in it); back leaves")
        got, *_ = disc_screen([["down"], ["right"], ["ok"]], have={"ps1": "sotn.cue"})
        check(got == "Randomizer", "after Back: the Randomizer, and the BIOS (until their own screens)")
        got, calls, _, _ = disc_screen([[], [("mouse", 8 + 157 + 20, 100, True)], ["back"]], have={"ps1": "sotn.cue"})
        check(calls == [("psp", None)], "the mouse: a click on the PSP slot browses for that disc")

        # Options
        import types

        import app
        from ui.screens.options import options
        from winmenu import MENUS
        fake = types.SimpleNamespace(settings={}, NETSIM_NAMES=app.Launcher.NETSIM_NAMES, bios=lambda: app.BUNDLED_BIOS)
        rows = app.Launcher.option_rows(fake)
        keys = {r["key"] for r in rows}

        def actions(items):
            for item in items:
                if item is None:
                    continue
                if isinstance(item[1], list):
                    yield from actions(item[1])
                else:
                    yield item[1]
        elsewhere = {"new", "continue", "quit", "rules", "settings",  # the main menu and the castle list have these; this is Settings
                     "pause", "report", "moment", "leave"}             # only in a game: the pause menu has them
        missing = sorted({a.split(":")[0] if a.startswith(("layout:", "netsim:")) else a for a in actions(MENUS)} - keys - elsewhere
                         - {"fullscreen"} if "_fullscreen" in keys else ["fullscreen"])
        check(not missing, f"every item in the window's menu bar is in Options, for a controller too: missing {missing}")
        changed = []
        m, ui, _ = menus([["down"], ["ok"], ["right"], ["back"]])
        check(options(m, lambda: rows, lambda k, st: changed.append((k, st))) is None and ui.names == ["Options"],
              "Options: back leaves")
        check(changed == [("_fullscreen", 0), ("_fullscreen", -1)],
              f"down skips the heading under it; OK toggles a switch, right turns it off (ON is drawn on the left): {changed}")
        m, ui, _ = menus([["up"], ["ok"]])
        check(options(m, lambda: rows, lambda k, st: None)[0] == "open_log", "up from the first row is the last: OK on an action returns it")

        app.ANDROID = True
        phone = {r["key"] for r in app.Launcher.option_rows(fake)}
        app.ANDROID = False
        check(not phone & {"_fullscreen", "data_folder", "open_log", "bios"} and "check_updates" in phone,
              "on a phone, Options leaves out fullscreen, folders, the log and the BIOS file")

        # A newer version
        from ui.screens.update import update_prompt
        m, ui, _ = menus([[], ["ok"]])
        check(update_prompt(m, "0.18.0", "0.17.0", ["A new thing"]) == "update" and "0.18.0" in ui.about,
              "an update: Update now is selected first")
        m, ui, _ = menus([["right"], ["ok"]])
        check(update_prompt(m, "0.18.0", "0.17.0", []) == "later", "Later is the other")
        m, ui, _ = menus([["back"]])
        check(update_prompt(m, "0.18.0", "0.17.0", []) == "later", "back is Later")
        found = iter([None, "update"])
        m, ui, _ = menus([[], []])
        check(home(m, ITEMS, about, "1.0", interrupt=lambda: next(found, "update")) == "update",
              "an update found while the main menu is up interrupts it")

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
