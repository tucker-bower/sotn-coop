"""The partner's inputs by frame, for its body's rollback in this game (#86, design/rollback.md).

The playout (link/playout.py) holds the partner's presences back to play them at an even pace. The
body doesn't wait for them: each frame the host gives the game every input the partner made, by the
partner's frame, as soon as it arrives (its buttons and its HP after the frame: INPT, with the last
frames again in each datagram, so one lost costs nothing), and the frame the partner is at now (where
the playout's clock says it is, plus half the round trip). The game's body runs up to that frame,
guessing the buttons that haven't come, and runs again from a wrong guess (module/partner.c).

Guesses (Slippi's input suggestions): the partner's app sends the buttons its player holds as soon as
it reads them, before its game runs the frame, and again whenever they change while it waits for the
next frame (SUGG). Those are what the body guesses with; a frame with none guesses the last buttons.
Only a guess: the frame's real buttons, from INPT, always decide.

Timing lives here, in the host (AGENTS.md); the game only sees buttons and frame numbers."""

from dataclasses import dataclass, field

ROLL_PADS = 32     # link.h: frames of inputs the game keeps
ROLL_GUESSES = 16  # link.h: frames of suggestions past the newest input
LEAD_MAX = 12      # never ask the body to guess further ahead than this (module/partner.c ROLL_LEAD)
INPUTS_SENT = 8    # frames of inputs in each INPT datagram


@dataclass
class Roll:
    """What Mailbox.write_roll writes for one partner."""
    newest: int
    target: int
    played: int
    inputs: dict = field(default_factory=dict)   # frame -> (buttons, HP or None)
    guesses: dict = field(default_factory=dict)  # frame -> buttons, past newest
    sprite: tuple = (0, (0, 0))                  # the sprites' frame, and where the partner stood then


class PadHistory:
    def __init__(self):
        self.reset()

    def reset(self):
        self.inputs = {}   # partner frame -> (buttons, HP after it or None)
        self.spots = {}    # partner frame -> (x, y) in the room, from its presence
        self.guesses = {}  # partner frame -> buttons it suggested, newest suggestion per frame
        self.newest = None
        self.sprite_frame = None

    def push(self, frame, pad, hp=None):
        """A frame's real input (INPT, or a presence's buttons)."""
        if self.newest is not None and frame <= self.newest - ROLL_PADS:
            return
        old = self.inputs.get(frame)
        self.inputs[frame] = (pad & 0xFFFF, hp if hp is not None else (old[1] if old else None))
        if self.newest is None or frame > self.newest:
            self.newest = frame
            for d in (self.inputs, self.spots):
                for f in [f for f in d if f <= frame - ROLL_PADS]:
                    del d[f]
            for f in [f for f in self.guesses if f <= frame]:
                del self.guesses[f]

    def spot(self, frame, x, y):
        self.spots[frame] = (x, y)

    def suggest(self, frame, pad):
        """A suggestion: the partner holds these buttons from this frame on (SUGG)."""
        if self.newest is not None and not 0 < frame - self.newest < ROLL_GUESSES:
            return
        self.guesses[frame] = pad & 0xFFFF

    def roll(self, now_frame, played):
        """The Roll for Mailbox.write_roll, or None before any input came."""
        if self.newest is None or played is None or played < 0:
            return None
        target = max(played, min(self.newest + LEAD_MAX, int(now_frame)))
        sprite = (0, (0, 0))
        if self.sprite_frame is not None:
            known = [f for f in self.spots if f <= self.sprite_frame]
            if known:
                sprite = (self.sprite_frame, self.spots[max(known)])
        return Roll(self.newest, target, played, dict(self.inputs), dict(self.guesses), sprite)


def inputs_payload(history):
    """INPT's payload from [(buttons, HP), ...], oldest first: the newest is the header's frame."""
    import struct
    rows = history[-INPUTS_SENT:]
    return struct.pack("<B", len(rows)) + b"".join(struct.pack("<HH", p & 0xFFFF, max(0, min(0xFFFE, h)))
                                                 for p, h in rows)


def read_inputs(frame, payload):
    """[(frame, buttons, HP)] from an INPT payload (nothing, if it's malformed)."""
    import struct
    if not payload:
        return []
    n = payload[0]
    if n > 64 or len(payload) < 1 + 4 * n:
        return []
    out = []
    for i in range(n):
        pad, hp = struct.unpack_from("<HH", payload, 1 + 4 * i)
        out.append((frame - (n - 1 - i), pad, hp))
    return out


# libretro's joypad bits (SwanStation: B cross, Y square, A circle, X triangle) -> the game's (PAD_*)
_PS = (0x40, 0x80, 0x100, 0x800, 0x1000, 0x4000, 0x8000, 0x2000, 0x20, 0x10, 0x4, 0x8, 0x1, 0x2, 0x200, 0x400)


def ps_buttons(mask):
    """A libretro joypad mask as the game's g_pads bits."""
    return sum(bit for i, bit in enumerate(_PS) if mask >> i & 1)
