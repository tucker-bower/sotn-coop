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
    import inspect
    import gameview
    src = inspect.getsource(gameview.GameView.set_rules)
    check('if self.rules["pvp"]:' in src and "CONTROL_PVP" in src, "the game view sets CONTROL_PVP only when the rules do")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
