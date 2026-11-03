"""Notices a game that has crashed or hung (issue 113). A write through a bad pointer overwrites
the exception vector, and a game spinning in its own code stops its timer, while the emulator runs
on either way. Only in play: the ending's movie and a load run outside the game's main loop."""

from link.mailbox import IN_PLAY

VECTOR, VECTOR_SIZE = 0x80000080, 16
EVERY = 60    # frames between checks
HUNG = 600    # frames with the game's timer stopped


class CrashWatch:
    def __init__(self):
        self.good, self.beats = {}, {}

    def check(self, games):
        """What's wrong with one of the games, for the report; None if nothing is."""
        for g in games:
            vector = g.read_bytes(VECTOR, VECTOR_SIZE)
            if self.good.setdefault(g.name, vector) != vector:
                return f"game {g.name} crashed: its exception vector was overwritten"
            p = g.mailbox("self_presence")
            seen, frames = self.beats.get(g.name, (None, 0))
            if p.frame != seen or not p.flags & IN_PLAY:
                self.beats[g.name] = (p.frame, 0)
            elif frames + EVERY >= HUNG:
                return f"game {g.name} hung: its timer stopped at {p.frame}"
            else:
                self.beats[g.name] = (seen, frames + EVERY)
        return None
