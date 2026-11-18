"""Boss rush (docs/design/boss-rush.md): launcher/bossrush.py driving two games through the joint
save, as the launcher does on the couch."""

import sys
from pathlib import Path

from session import MailboxProxy, session_scenario  # first: puts `link` on the path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
import bossrush  # noqa: E402
from link.jointsave import JointSave  # noqa: E402
from link.mailbox import BUSY, IN_PLAY  # noqa: E402
from session_m12 import boss_flow, _bossstarts  # noqa: E402

GAME_ENDING = 9


def drive(run, rush, joint, cond, limit):
    """Frames as the launcher runs them: the games, the joint save, the rush. True once cond()."""
    for _ in range(limit):
        if cond():
            return True
        run.step(1)
        joint.tick()
        rush.tick()
    return cond()


def row(name):
    return next(r for r in _bossstarts() if r["name"] == name)


@session_scenario()
def online_boss_rush(run):
    """Online (two hosts over UDP): the host's rush loads the first boss for both; the boss falls
    (its record, written: the fight is the other tests'); both load into the second boss, the
    joiner through the host's load_save."""
    from session_m11 import data, link, online, until
    from test_castles import pc
    from archive import Castle
    from link.mailbox import IN_PLAY
    with pc(data("A")):
        c = Castle.new(name="Boss rush")
    with online("entrance", 0, c) as s0, online("entrance", 1) as s1:
        link(s0, s1)
        until(s0, s1, lambda: s0.local.mailbox("partner_presence").flags & IN_PLAY, 600)
        rush = bossrush.BossRush(s0.joint, [s0.local], {})
        rows = rush.rows

        def both_at(k):
            stage, room = rows[k]["start"][:2]
            return all((lambda p: p.stage == stage and p.room_id == room and p.flags & IN_PLAY)(
                s.local.mailbox("self_presence")) for s in (s0, s1))

        def go(cond, frames):
            for _ in range(frames):
                if cond():
                    return True
                s0.step(1)
                s1.step(1)
                rush.tick()
            return cond()
        rush.load()
        run.expect(go(lambda: both_at(0), 2400), "both at the first boss",
                   a=s0.local.snapshot(), b=s1.local.snapshot())
        s0.local.write("g_Settings", 1, "<i", bossrush.RECORDS + 4 * bossrush.EVENTS[rows[0]["name"]])
        run.expect(go(lambda: rush.state["index"] == 1, 600), "the host's rush moves on", state=rush.state)
        run.expect(go(lambda: both_at(1), 2400), "both at the second boss, the joiner too",
                   a=s0.local.snapshot(), b=s1.local.snapshot())
