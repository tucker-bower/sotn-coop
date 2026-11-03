"""Sound through uneven frames (issue 134): a slow frame costs one short gap, not a crackle."""

import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from gameview import Audio  # noqa: E402

CHUNK, FRAME = 1024 * 4, 735 * 4  # bytes: what the device takes, and what a game's frame makes


def play(seconds, slow_every=0):
    """One game frame's sound every 1/60 s, some late; the device pulling on its own clock."""
    audio = Audio.__new__(Audio)
    audio.__dict__.update(buf=bytearray(), primed=False, underruns=0, short_bytes=0, pulls=0, pushes=0,
                          clipped=0, dropped_bytes=0, chan=None)
    import threading
    audio.lock = threading.Lock()
    rng, pull_at = random.Random(1), 0.0
    for f in range(seconds * 60):
        t = f / 60 + (0.012 * rng.random() if rng.random() < 0.2 else 0)
        if slow_every and f % slow_every == 0:
            t += 0.05
        while pull_at < t:
            mem = bytearray(CHUNK)
            audio._pull(None, mem)
            pull_at += 1024 / 44100
        audio.push(bytes([1, 0]) * (FRAME // 2))
    return audio


failed = []


def check(ok, what):
    print(("ok  " if ok else "FAIL"), what)
    if not ok:
        failed.append(what)


audio = play(60)
check(audio.underruns == 0, f"a minute of uneven frames: {audio.underruns} underruns")
audio = play(60, slow_every=300)
check(audio.underruns <= 12, f"a slow frame every 5 s: {audio.underruns} underruns, at most one each")
print("all passed" if not failed else f"{len(failed)} FAILED")
sys.exit(1 if failed else 0)
