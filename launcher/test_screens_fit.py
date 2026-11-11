"""No text is cut off (issue 232): every screen in the game's style is drawn with long, realistic
content (long castle names, every rule, both players' cards, the longest disc errors), and any
line that runs past the window it's in fails the test. Made-up art: no game data is needed.

    python launcher/test_screens_fit.py
"""

import os
import sys
import tempfile
import time
import types
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent / "patcher")]

import pygame  # noqa: E402

import test_ui  # noqa: E402  (its made-up art, inputs and castles)
from ui.theme import Theme  # noqa: E402
from ui.widgets import Menus  # noqa: E402

LONG = "Tucker's very long castle name"
failures = []


def main():
    pygame.init()
    with tempfile.TemporaryDirectory() as d:
        test_ui.made_up_art(d)
        theme = Theme(d)
        cut = []

        def screen(name, run, frames=((), ("back",))):
            ui = test_ui.Inputs([list(f) for f in frames] + [["back"]] * 3)
            m = Menus(ui, theme, None)
            m.device = "pad"
            show = m.show

            def shown():
                cut.extend((name, *o) for o in theme.overflows)
                show()
            m.show = shown
            try:
                run(m)
            except AssertionError:
                pass  # (ran out of scripted input: the screen was drawn)

        from ui.screens.castle_settings import castle_settings
        from ui.screens.castles import castle_list, castle_menu
        from ui.screens.discs import discs
        from ui.screens.home import home
        from ui.screens.lobby import draw_lobby
        from ui.screens.options import options
        from ui.screens.update import update_prompt
        import app
        import rules
        os.environ["COOP_DATA"] = d
        import library
        presets = {}
        for k in range(6):
            library.add(presets, [{"kind": "hacks", "ids": ["fast-warp", "minimap", "quick-items"]},
                                  {"kind": "randomizer", "file": "x.sdif", "info": {"seed": "abcdefghij", "preset": "lycanthrope-spr26te", "version": "26.07.13"}}],
                        None if k % 2 else "A long preset name here")
        castle = test_ui.Castle(LONG, 3, "Olrox's Quarters", 99, "Rules changed: XP gain, Enemy HP, alone, Damage taken, PvP")
        castle.info["created"] = time.time() - 9e6
        items = [("solo", "Solo", ""), ("couch", "Couch co-op", ""), ("online", "Online co-op", ""), ("discs", "Discs", ""),
                 ("mods", "Mods", ""), ("settings", "Options", ""), ("quit", "Quit", "")]
        for k, key in enumerate(i[0] for i in items):
            about = app.Launcher.home_about(types.SimpleNamespace(characters=[0, 0], maria_ready=lambda: True, saturn_maria_ready=lambda: False,
                                                                  settings=presets,
                                                                  mod_line=lambda: "Randomizer seed abcdefgh · casual (26.07.13) + Fast Warp"), key) \
                if hasattr(app.Launcher, "home_about") else {}
            if key in ("solo", "couch", "online"):
                about = {"lines": ["Your last castle"], "castle": castle, "portrait": "alucard"}
            screen(f"home: {key}", lambda m, k=k, a=about: home(m, items, lambda _: a, "0.18.1", sel=k,
                                                               note="Version 0.19.0 is out"), frames=((), ("back",), ("ok",)))
        for heading in ("Solo", "Couch co-op", "Online co-op: host"):
            for sel in range(3):
                screen(f"castle menu: {heading}", lambda m, h=heading: castle_menu(m, h, castle, True,
                       note="New castles are on randomizer seed abcdefgh · casual (26.07.13)"),
                       frames=[()] + [("down",)] * sel + [("back",)])
        castles = [castle] + [test_ui.Castle(f"{LONG} {k}", k, "Marble Gallery", k) for k in range(12)]
        screen("castle list", lambda m: castle_list(m, "Load castle", castles, [("tests", "Test castles", "Outside each boss and before each story scene, with a typical player's progress")]))
        r = rules.clean({"pvp": True, "remap": True})
        n = len([1 for _ in rules.GROUPS for _ in _[1]]) + 20
        screen("castle settings (new)", lambda m: castle_settings(m, LONG, r, lambda x: None, start=True, mode={"mode": "rush"}),
               frames=[()] + [("down",)] * n + [("back",)])
        mode = {"mode": "story", "preset": None, "presets": [(None, library.PLAIN)] + [(g["id"], library.name(g)) for g in library.discs(presets)]}
        screen("castle settings (new, a preset chosen)", lambda m: castle_settings(m, LONG, dict(r), lambda x: None, start=True, mode=mode),
               frames=[(), ("down",), ("down",), ("right",), ("right",), ("back",)])
        rows_ = app.Launcher.preset_rows(types.SimpleNamespace(settings=presets))
        screen("mods", lambda m: options(m, lambda: rows_, lambda *a: None, title="Mods", note="Your partner needs the same preset"),
               frames=[()] + [("down",)] * len(rows_) + [("back",)])
        from ui.screens.pick import pick
        from ui.screens.progress import progress
        from ui.screens.text_entry import text_entry
        screen("pick", lambda m: pick(m, "Online co-op", [("host", "Host", "Choose a castle; you get a room code to give your partner."),
                                                          ("join", "Join", "Type your partner's room code: you play their castle, and keep a copy.")],
                                      "Both of you need the same version of SOTN Co-op."), frames=[(), ("down",), ("back",)])
        screen("text entry", lambda m: text_entry(m, "Name your mod preset", "Randomizer seed abcdefghij · lycanthrope-spr26te (26.07.13) + Fast Warp, MiniMap, Quick Items",
                                                 "A very long name typed into the box, longer than it", pad="{x} done   {s} paste   {o} back",
                                                 keys="Type   Ctrl+V: paste   Enter: done   Esc: back"), frames=[()])
        import threading
        gate = threading.Event()
        screen("progress", lambda m: progress(m, "Building modded disc", "A long preset name here: Seed abcdefghij + Fast Warp and 2 more",
                                              lambda report: (report(3, 10), gate.wait(0.3))), frames=[()] * 40)
        screen("castle settings (joiner)", lambda m: castle_settings(m, LONG, dict(r), lambda x: None, read_only=True),
               frames=[()] + [("down",)] * n + [("back",)])
        long_error = ("This is the USA disc, but not an exact copy: it may be a damaged or modified rip. A clean rip (one "
                      "that matches redump.org) is needed. And then some more words to be sure it wraps.")
        for first in (True, False):
            screen(f"discs (first run: {first})", lambda m, f=first: discs(m, lambda: {"ps1": "Castlevania - Symphony of the Night (USA) (Track 1).bin",
                                                                                       "psp": "Castlevania - The Dracula X Chronicles (USA).iso"},
                                                                           lambda *a: (None, "", True), f, long_error),
                   frames=((), ("down",), ("right",), ("back",)))
        rows = app.Launcher.option_rows(types.SimpleNamespace(settings={"netsim": "transatlantic"}, NETSIM_NAMES=app.Launcher.NETSIM_NAMES,
                                                              bios=lambda: Path("C:/a/very/long/path/to/someones-own-console-bios-scph5501.bin")))
        screen("options", lambda m: options(m, lambda: rows, lambda *a: None), frames=[()] + [("down",)] * len(rows) + [("back",)])
        screen("update", lambda m: update_prompt(m, "0.19.0", "0.18.1", ["A much longer changelog item than usual, to see it wrap well"] * 8))
        card = {"title": "Player 2", "joined": True, "device": "DualSense Wireless Controller", "ready": False, "character": 5,
                "name": "Ultimate Richter", "playable": False, "note": "From SOTN Ultimate: the Saturn coat",
                "needs": "Attach your Saturn disc (Japan) to unlock him.", "controls": "L2 high jump, R2 dash", "shortcuts": True}
        ready = dict(card, title="Player 1", character=4, name="Saturn Maria", playable=True, ready=True, note="From SOTN Ultimate: Saturn Maria")
        for name, cards, partner in (("lobby: couch", [ready, card], None),
                                     ("lobby: host", [ready], (["It's on your clipboard:", "send it to them.", "",
                                                               "Waiting for your partner's game: 4:52 left"], False, "BAT-7K2Q")),
                                     ("lobby: joined", [card], (["Connected!", "ping 142 ms"], True, None))):
            screen(name, lambda m, c=cards, p=partner: draw_lobby(m, "Who's playing?", "Player 1: left screen. 2: right.", c, p,
                                                                   ("{<}{>} character   {t} shortcuts   {x} ready   {o} leave", "keys")),
                   frames=())
        seen = set()
        cut = [c for c in cut if not ((c[0], c[1]) in seen or seen.add((c[0], c[1])))]  # (each once)
        for name, *where in cut[:20]:
            print(f"FAIL {name}: {where[0]!r} runs past its window {where[3]} (at x {where[1]}, y {where[2]})")
        print(f"ok   every screen drawn, {len(cut)} lines cut off" if not cut else f"\n{len(cut)} lines cut off")
        if cut:
            failures.append("cut off")
    print(f"\n{'all passed' if not failures else 'FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
