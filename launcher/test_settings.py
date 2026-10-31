"""Settings defaults (no games run): PvP is optional and off on a fresh install (M15, Tucker
2026-10-31), and the game gets the PvP bit only when it's on.

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
        check(s["pvp"] is False, "a fresh install: PvP off")
        s["pvp"] = True
        paths.save_settings(s)
        check(paths.load_settings()["pvp"] is True, "turned on, it stays on")
        s["pvp"] = False
        paths.save_settings(s)
        check(paths.load_settings()["pvp"] is False, "and off again")
    # the control word the game gets (gameview.GameView: CONTROL_PVP only with pvp=True)
    import inspect
    import gameview
    src = inspect.getsource(gameview.GameView.__init__)
    check("pvp=False" in inspect.signature(gameview.GameView.__init__).__str__() and
          "if pvp:" in src and "CONTROL_PVP" in src, "the game view sets CONTROL_PVP only when asked (default off)")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
