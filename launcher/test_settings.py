"""Settings defaults (no games run): the app's settings stay the app's, and the rules that used to
be here (PvP, boss aggro) are each castle's now (launcher/test_rules.py, D162). The game gets the
PvP bit only when the castle's rules say so.

    python launcher/test_settings.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main():
    with tempfile.TemporaryDirectory() as d:
        os.environ["COOP_DATA"] = d
        import paths
        s = paths.load_settings()
        check("pvp" not in s and "aggro" not in s, "a fresh install has no global PvP or aggro setting")
        s["music"] = "left"
        paths.save_settings(s)
        check(paths.load_settings()["music"] == "left", "a setting stays as it's set")

        # Alucard's spells on the right stick: each player's own switch, in Your settings
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import types
        import app
        from link.mailbox import spell_options
        f = types.SimpleNamespace(settings={}, refresh_players=lambda: None, wide_shape=lambda: 0, bios=lambda: Path("bios.bin"),
                                  NETSIM_NAMES=app.Launcher.NETSIM_NAMES)
        for name in ("stick_spells", "spells", "shortcuts", "option_rows", "button_rows", "change_option"):
            setattr(f, name, getattr(app.Launcher, name).__get__(f))
        f.button_rows = lambda seat: []
        keys = [r["key"] for r in app.Launcher.player_rows(f)]
        check("stick_spells:0" in keys and "stick_spells:1" in keys and keys.index("stick_spells:0") < keys.index("spell:0:0"),
              "Your settings: each player's switch, just above their four spells")
        stick = spell_options(app.DEFAULT_SPELLS)
        check(app.Launcher.options(f, 0) & stick == stick, "on to start with: the game gets the player's spells")
        app.Launcher.change_player(f, "stick_spells:1", 0)
        check(app.Launcher.options(f, 1) & stick == 0 and app.Launcher.options(f, 0) & stick == stick
              and paths.load_settings().get("stick_spells") == [True, False],
              "player 2 turns theirs off: their game gets none, player 1's is unchanged, and it's saved")
        check(all(app.Launcher.controls_line(f, c, True) == "" for c in range(6)) and app.Launcher.controls_line(f, 0, False),
              "character select lists no character's shortcuts (they're optional); it only says when they're off")
    import inspect
    import gameview
    src = inspect.getsource(gameview.GameView.set_rules)
    check('if self.rules["pvp"]:' in src and "CONTROL_PVP" in src, "the game view sets CONTROL_PVP only when the rules do")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
