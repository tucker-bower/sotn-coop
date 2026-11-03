"""Sound through uneven frames (issue 134): a slow frame costs one short gap, not a crackle."""

import collections
import os
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from gameview import Audio, Pacer  # noqa: E402

CHUNK, FRAME = 1024 * 4, 735 * 4  # bytes: what the device takes, and what a game's frame makes


def play(seconds, slow_every=0):
    """One game frame's sound every 1/60 s, some late; the device pulling on its own clock."""
    audio = Audio.__new__(Audio)
    audio.__dict__.update(buf=bytearray(), primed=False, fed_bytes=0, started=0, pushed_at=0.0, push_gap=0.0, underruns=0, short_bytes=0, pulls=0, pushes=0,
                          clipped=0, dropped_bytes=0, chan=None, queue=None)
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


class Channel:
    """SDL_mixer's channel on a simulated clock: one sound playing, at most one queued behind it,
    which starts the moment the first ends. Counts the time it sits silent."""

    def __init__(self, clock):
        self.clock, self.end, self.queued, self.silent, self.last = clock, None, None, 0.0, 0.0

    def _advance(self):
        now = self.clock[0]
        while self.end is not None and self.end <= now:
            if self.queued is not None:
                self.end, self.queued = self.end + self.queued, None
            else:
                self.last, self.end = self.end, None
        return now

    def get_busy(self):
        self._advance()
        return self.end is not None

    def get_queue(self):
        self._advance()
        return self.queued

    def play(self, sound):
        now = self._advance()
        if self.end is None:
            self.silent += now - self.last
        self.end, self.queued = now + sound, None

    def queue(self, sound):
        if self.get_busy():
            self.queued = sound
        else:
            self.play(sound)

    def stop(self):
        self._advance()
        self.last, self.end, self.queued = self.clock[0], None, None


def play_mixer(seconds, fps=62, seed=1):
    """Android's path (SDL_mixer, fed from the main thread, design/M9): frames at the app's rate
    with the scheduling jitter of a phone, each pushing a game frame's sound."""
    import gameview
    clock = [0.0]
    gameview.time.monotonic = lambda: clock[0]
    gameview.pygame.mixer.Sound = lambda buffer: len(buffer) / (44100 * 4)  # a sound: its length
    audio = Audio.__new__(Audio)
    audio.__dict__.update(buf=bytearray(), primed=False, fed_bytes=0, started=0, underruns=0, short_bytes=0,
                          pulls=0, pushes=0, clipped=0, dropped_bytes=0, chan=Channel(clock), queue=None, fed_at=0.0, pushed_at=0.0, push_gap=0.0, gaps=collections.deque(maxlen=30))
    import threading
    audio.lock = threading.Lock()
    rng = random.Random(seed)
    for f in range(int(seconds * fps)):
        clock[0] = f / fps + 0.006 * rng.random() + (0.02 if rng.random() < 0.01 else 0)
        audio.push(bytes([1, 0]) * (FRAME // 2))
    clock[0] += 1
    audio.chan.get_busy()
    return audio, audio.chan.silent


class Queue:
    """SDL_QueueAudio on a simulated clock: SDL plays what's queued in real time."""

    def __init__(self, clock):
        self.clock, self.bytes, self.at = clock, 0, 0.0

    def queued(self):
        played = int((self.clock[0] - self.at) * 44100) * 4
        self.bytes, self.at = max(0, self.bytes - played), self.clock[0]
        return self.bytes

    def push(self, data):
        self.queued()
        self.bytes += len(data)

    def clear(self):
        self.bytes = 0


def play_queue(seconds, fps=62, seed=1):
    """Android's path since issue 66: SDL_QueueAudio, from the main thread."""
    import gameview
    clock = [0.0]
    gameview.time.monotonic = lambda: clock[0]
    audio = Audio.__new__(Audio)
    audio.__dict__.update(buf=bytearray(), primed=False, fed_bytes=0, started=0, underruns=0, short_bytes=0,
                          pulls=0, pushes=0, clipped=0, dropped_bytes=0, chan=None, queue=Queue(clock),
                          pushed_at=0.0, push_gap=0.0, gaps=collections.deque(maxlen=30))
    import threading
    audio.lock = threading.Lock()
    rng = random.Random(seed)
    for f in range(int(seconds * fps)):
        clock[0] = f / fps + 0.006 * rng.random() + (0.02 if rng.random() < 0.01 else 0)
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
audio, silent = play_mixer(60)
check(audio.underruns <= 3 and silent < 0.2,
      f"Android's mixer, a minute at 62 fps with a phone's jitter: {audio.underruns} underruns, {silent * 1000:.0f} ms silent")
audio = play_queue(60, fps=60)
check(audio.underruns == 0 and audio.dropped_bytes == 0,
      f"SDL's queue (Android), a minute at 60 fps with a phone's jitter: {audio.underruns} underruns, "
      f"{audio.dropped_bytes / 176.4:.0f} ms dropped")
import time  # noqa: E402
pacer, t0 = Pacer(), time.perf_counter()
for _ in range(60):
    pacer.wait()
took = time.perf_counter() - t0
check(0.99 <= took <= 1.03, f"the pacer: 60 frames in {took:.3f} s (Clock.tick(60) on Android's pygame: 0.96)")
try:
    from sdlqueue import SdlQueue
    q = SdlQueue()
    q.push(bytes(735 * 4))
    check(q.queued() > 0, f"the real SDL queue opens and takes sound ({q.queued()} bytes waiting)")
    q.clear()
    check(q.queued() == 0, "and clears")
    q.close()
except OSError as e:
    check(False, f"the real SDL queue: {e}")
print("all passed" if not failed else f"{len(failed)} FAILED")
sys.exit(1 if failed else 0)
