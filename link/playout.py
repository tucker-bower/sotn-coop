"""The partner's state, played back at an even pace (a jitter buffer).

Online, the partner's presences and room snapshots arrive bunched up and with gaps: two in one
frame, then none for three. Written to the game as they come, the partner's puppet and the
shared enemies stutter. The playout holds them for a short, adaptive delay and hands the game
one frame's worth per frame, in the sender's frame order, interpolating the puppet's position
across a lost presence.

Times are the receiver's clock (s); frames are the sender's host frames (link/transport.py).
- offset: arrival time minus the sender's frame time. Its minimum over the last few seconds is
  the fastest the network has been; anything above it is jitter. When even the most recent
  offsets all sit well above that minimum, the path itself changed (a slower route, or the
  partner's PC hitched and its frames now run later): the minimum starts over.
- delay: how far behind that fastest path we play. It rises at once to cover the jitter seen
  (95th percentile) and falls back slowly, so it doesn't pump. While presences go missing it's
  at least a frame, so a lost one is interpolated across instead of showing as a hitch.
Everything here is host-side and timing-dependent by nature (AGENTS.md): the game only ever
sees ordinary presence and snapshot writes."""

import bisect
import collections
from dataclasses import replace

FPS = 60
WINDOW_S = 3.0       # the jitter is measured over this long
REBASE_S = 0.3       # if every offset this recent is well above the fastest path, it moved
MAX_DELAY_S = 0.25   # never hold the partner back more than this
DECAY_S = 0.02       # the delay falls back by at most this much per second
MAX_LERP = 6         # interpolate across at most this many missing frames
MAX_STEP = 48        # ...and only if the partner moved less than this (px) between samples


class Playout:
    def __init__(self, fps=FPS):
        self.fps = fps
        self._offsets = collections.deque()   # (arrival, offset)
        self._frames = []                     # sorted sender frames with a presence waiting
        self._pres = {}                       # frame -> Presence
        self._snaps = collections.deque()     # (frame, snapshot), in frame order
        self.delay = 0.0
        self.min_delay = 0.0   # the host raises it to a frame when presences go missing
        self._last_t = None
        self.played = -1       # newest sender frame whose presence was written
        self._played_pres = None
        self.snap_played = -1
        self.late = 0          # presences that came after their frame was already played

    def reset(self):
        self.__init__(self.fps)

    def _note_arrival(self, now, frame):
        off = now - frame / self.fps
        q = self._offsets
        q.append((now, off))
        while q and q[0][0] < now - WINDOW_S:
            q.popleft()

    def push_presence(self, now, frame, presence):
        self._note_arrival(now, frame)
        if frame <= self.played:
            self.late += 1
            return
        if frame not in self._pres:
            bisect.insort(self._frames, frame)
        self._pres[frame] = presence

    def push_snapshot(self, now, frame, snap):
        self._note_arrival(now, frame)
        if frame <= self.snap_played:
            return
        self._snaps.append((frame, snap))
        if len(self._snaps) > 1 and self._snaps[-2][0] > frame:  # out of order: keep them sorted
            self._snaps = collections.deque(sorted(self._snaps, key=lambda x: x[0]))

    def _update_delay(self, now):
        if not self._offsets:
            return None
        q = self._offsets
        recent = [o for t, o in q if t >= now - REBASE_S]
        base = min(o for _, o in q)
        if recent and min(recent) - base > 2 / self.fps:
            # The path got slower for good, or the partner's PC hitched (its frames are now
            # later than before): start over from here instead of calling it jitter.
            while q and q[0][0] < now - REBASE_S:
                q.popleft()
            base = min(recent)
        offs = sorted(o for _, o in q)
        p95 = offs[min(len(offs) - 1, int(len(offs) * 0.95))] - base
        want = min(MAX_DELAY_S, max(self.min_delay, p95))
        if want >= self.delay:
            self.delay = want
        elif self._last_t is not None:
            self.delay = max(want, self.delay - DECAY_S * (now - self._last_t))
        self._last_t = now
        return base

    def pop(self, now):
        """(presence or None, snapshot or None): what to write to the game this frame."""
        base = self._update_delay(now)
        if base is None:
            return None, None
        play = (now - base - self.delay) * self.fps  # the sender's frame to show now
        snap = None
        while self._snaps and self._snaps[0][0] <= play + 1e-6:
            f, snap = self._snaps.popleft()
            self.snap_played = f
        return self._presence_at(play), snap

    def _presence_at(self, play):
        fr = self._frames
        i = bisect.bisect_right(fr, play + 1e-6)  # fr[:i] are due
        if i == 0:
            # Nothing due yet. Between the last one written and the next one to come?
            if fr and self._played_pres is not None:
                return self._lerp(self.played, self._played_pres, fr[0], self._pres[fr[0]], play)
            return None
        fa = fr[i - 1]
        a = self._pres[fa]
        for f in fr[:i - 1]:
            del self._pres[f]
        del fr[:i - 1]
        # fa is due: the newest due sample. Is the next one here, to interpolate towards?
        out = a
        if len(fr) > 1 and play > fa:
            out = self._lerp(fa, a, fr[1], self._pres[fr[1]], play) or a
        del self._pres[fa]
        del fr[0]
        self._played_pres, self.played = a, fa
        return out

    def _lerp(self, fa, a, fb, b, play):
        """a (frame fa) and b (frame fb), interpolated at frame `play`, when it makes sense:
        same room, a short gap, a small move. Otherwise None (keep showing what's there)."""
        if not (fa < play < fb) or fb - fa > MAX_LERP or (a.stage, a.room_left, a.room_top) != (b.stage, b.room_left, b.room_top):
            return None
        if abs(b.x - a.x) > MAX_STEP or abs(b.y - a.y) > MAX_STEP:
            return None
        k = (play - fa) / (fb - fa)
        lerp = lambda u, v: round(u + (v - u) * k)
        return replace(a, x=lerp(a.x, b.x), y=lerp(a.y, b.y),
                       scroll_x=lerp(a.scroll_x, b.scroll_x), scroll_y=lerp(a.scroll_y, b.scroll_y))

    def stats(self):
        return {"delay_ms": round(self.delay * 1000), "late": self.late,
                "waiting": len(self._frames), "snaps_waiting": len(self._snaps)}
