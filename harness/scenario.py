"""Scenario runner: start from a savestate, drive inputs or bots, assert on RAM, write evidence.

A scenario is a function decorated with @scenario(start=...). It gets a Run and uses
run.play()/run.step() to advance and run.expect() to assert. Each run writes
.env/out/<name>/report.json and clip.gif (PR evidence).
"""

import json
import time
import traceback

from coop_env import DISKS, TOOLS, savestate
from emu import Emu

SCENARIOS = {}


def scenario(start, disc=None):
    def register(fn):
        SCENARIOS[fn.__name__] = (fn, start, disc)
        return fn
    return register


class Failed(AssertionError):
    pass


class Run:
    def __init__(self, emu, name, gif_every=12):
        self.emu, self.name = emu, name
        self.checks, self.rooms = [], []
        self._gif_every, self._frames = gif_every, []

    def _after_frame(self):
        s = self.emu.snapshot()
        if not self.rooms or self.rooms[-1]["room"] != list(s["room"]):
            self.rooms.append({"room": list(s["room"]), "stage": s["stage"], "frame": s["frame"]})
        if s["frame"] % self._gif_every == 0:
            img = self.emu.screenshot()
            if img:  # half size: about 1MB per 20 s of play
                self._frames.append(img.resize((img.width // 2, img.height // 2)))
        return s

    def step(self, n=1, p1=0, p2=0):
        for _ in range(n):
            self.emu.step(1, p1, p2)
            self._after_frame()
        return self.emu.snapshot()

    def play(self, bot, frames, until=None, p2_bot=None):
        """Runs bot(s) for up to `frames`; stops early when until(snapshot) is true. Returns snapshot."""
        s = self.emu.snapshot()
        for i in range(frames):
            if until and until(s):
                break
            self.emu.step(1, bot(s, i), p2_bot(s, i) if p2_bot else 0)
            s = self._after_frame()
        return s

    def expect(self, ok, what, **details):
        self.checks.append({"ok": bool(ok), "what": what, "frame": self.emu.frame, **details})
        if not ok:
            raise Failed(f"{what} {details}")

    def save_gif(self, path):
        if self._frames:
            self._frames[0].save(path, save_all=True, append_images=self._frames[1:],
                                 duration=self._gif_every * 1000 // 60, loop=0, optimize=True)


def run_scenario(name):
    fn, start, disc = SCENARIOS[name]
    out = TOOLS["out"] / name
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    disc = disc or DISKS / "sotn.us.cue"
    with Emu(disc) as emu:
        emu.load_state_file(savestate(disc, start))
        frame0 = emu.frame
        run = Run(emu, name)
        error = None
        try:
            fn(run)
        except Failed as exc:
            error = f"assertion failed: {exc}"
        except Exception:
            error = traceback.format_exc()
        report = {
            "scenario": name, "start": start, "passed": error is None, "error": error,
            "frames": emu.frame - frame0, "seconds": round(time.time() - t0, 1),
            "checks": run.checks, "rooms": run.rooms, "final": emu.snapshot(),
        }
        run.save_gif(out / "clip.gif")
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report
