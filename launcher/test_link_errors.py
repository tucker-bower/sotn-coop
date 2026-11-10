"""Checks that a failure in the link never stops a player's game.

    python launcher/test_link_errors.py

In real-time play each game's worker runs the host after every frame (harness/session.py). The
host failing (a bug of ours, or something from the network no test thought of) must cost the
partner, not the session: the game's frame still comes back, and the failure is in the log."""

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "harness")]

from session import _Worker  # noqa: E402


class Emu:
    steps = 0

    def step(self, n, pad):
        self.steps += n

    def raw_frame(self):
        return None

    def take_audio(self):
        return b"sound"


class Host:
    frames = 0

    def after_frame(self):
        self.frames += 1
        raise ValueError("the link broke")


def main():
    records = []
    handler = logging.Handler()
    handler.emit = records.append
    logging.getLogger("link").addHandler(handler)
    logging.getLogger("link").propagate = False

    w = _Worker.__new__(_Worker)  # a worker with no game: only what "frame" and "step" touch
    w.emu, w.host, w.shm, w.linked = Emu(), Host(), None, True
    w.clock, w.host_ms = {"t": 0.0, "dt": 1 / 60}, []
    failures = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    replies = [w.handle("frame", 0) for _ in range(20)]
    check(all(r == (None, b"sound") for r in replies) and w.emu.steps == 20,
          "the host fails every frame: 20 frames of the game still come back, with their sound")
    check(w.host.frames == 20, "the host is still run every frame (it may recover)")
    check(len(records) == _Worker.LINK_ERRORS_LOGGED and records[0].exc_info and w.link_errors == 20,
          f"the first {_Worker.LINK_ERRORS_LOGGED} failures are logged with their traceback, and all are counted")
    try:
        w.handle("step", (1, 0))
        check(False, "a test's step raises what the host raised")
    except ValueError:
        check(True, "a test's step raises what the host raised")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
