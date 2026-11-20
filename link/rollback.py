"""The partner's buttons by frame, for its body's rollback in this game (#86, design/rollback.md).

The playout (link/playout.py) holds the partner's presences back to play them at an even pace. The
body doesn't wait for them: each frame the host gives the game every button the partner pressed,
by the partner's frame, as soon as it arrives, and the frame the partner is at now (where the
playout's clock says it is, plus half the round trip). The game's body runs up to that frame,
guessing the buttons that haven't come, and runs again from a wrong guess (module/partner.c).
Timing lives here, in the host (AGENTS.md); the game only sees buttons and frame numbers."""

ROLL_PADS = 32   # link.h: frames of buttons the game keeps
LEAD_MAX = 12    # never ask the body to guess further ahead than this (module/partner.c ROLL_LEAD)


class PadHistory:
    def __init__(self):
        self.reset()

    def reset(self):
        self.pads = {}     # partner frame -> its buttons
        self.newest = None

    def push(self, frame, pad):
        if self.newest is not None and frame <= self.newest - ROLL_PADS:
            return  # too old to matter
        self.pads[frame] = pad & 0xFFFF
        if self.newest is None or frame > self.newest:
            self.newest = frame
            for f in [f for f in self.pads if f <= frame - ROLL_PADS]:
                del self.pads[f]

    def roll(self, now_frame, played):
        """(newest, target, played, pads) for Mailbox.write_roll, or None before any came."""
        if self.newest is None or played is None or played < 0:
            return None
        target = max(played, min(self.newest + LEAD_MAX, int(now_frame)))
        return self.newest, target, played, dict(self.pads)
