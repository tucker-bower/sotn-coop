"""Simple scripted bots. A bot is a function (snapshot, frame_index) -> buttons for this frame."""


def walker(direction="right", attack_every=0, jump_when_stuck=True):
    """Walks one way; optionally attacks every N frames and jumps when it stops making progress."""
    last_x, stuck = None, 0

    def bot(s, i):
        nonlocal last_x, stuck
        stuck = stuck + 1 if s["world_x"] == last_x else 0
        last_x = s["world_x"]
        buttons = [direction]
        if attack_every and i % attack_every < 2:
            buttons.append("square")
        if jump_when_stuck and stuck > 10 and i % 30 < 15:
            buttons.append("cross")
        return "+".join(buttons)

    return bot


def idle(s, i):
    return 0
