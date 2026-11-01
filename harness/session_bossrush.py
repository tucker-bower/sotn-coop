"""Boss rush (docs/design/boss-rush.md): launcher/bossrush.py driving two games through the joint
save, as the launcher does on the couch."""

import sys
import tempfile
from pathlib import Path

from session import MailboxProxy, session_scenario  # first: puts `link` on the path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
import bossrush  # noqa: E402
from link.jointsave import JointSave  # noqa: E402
from link.mailbox import BUSY, IN_PLAY  # noqa: E402
from session_m12 import boss_flow, _bossstarts  # noqa: E402

GAME_ENDING = 9


def rush_at(run, name):
    """A boss rush whose current boss is `name`, loaded into both games (at its start)."""
    a, b = run.s.a, run.s.b
    path = Path(tempfile.mkdtemp(prefix="coop-rush-")) / "castle.coop"
    joint = JointSave([MailboxProxy(a), MailboxProxy(b)], path)
    rush = bossrush.BossRush(joint, (a, b), {})
    rush.state["index"] = [r["name"] for r in rush.rows].index(name)
    rush.load()
    run.expect(at_start(run, rush, joint), f"both load into {name}'s start", a=a.snapshot(), b=b.snapshot())
    return rush, joint


def drive(run, rush, joint, cond, limit):
    """Frames as the launcher runs them: the games, the joint save, the rush. True once cond()."""
    for _ in range(limit):
        if cond():
            return True
        run.step(1)
        joint.tick()
        rush.tick()
    return cond()


def at_start(run, rush, joint, limit=2400):
    stage, room = rush.boss["start"][:2]

    def there():
        return all((lambda p: p.stage == stage and p.room_id == room and p.flags & IN_PLAY)(g.mailbox("self_presence"))
                   for g in (run.s.a, run.s.b))
    return drive(run, rush, joint, there, limit)


def drive_fight(run, rush, joint, b, until, limit=12000):
    """A walks in and both fight, as boss_flow's loop does (worn down, a scripted last hit),
    with the rush ticking: True once until()."""
    from session_m12 import FIGHT_FREE, FLAG_DEAD, enemies, fight_pad
    from link.mailbox import BOSS, ROLE_AUTHORITY
    a, g2 = run.s.a, run.s.b
    free = 0
    for t in range(limit):
        if until():
            return True
        pa = a.mailbox("self_presence")
        boss_here = pa.flags & BOSS
        auth = a if pa.role == ROLE_AUTHORITY else g2
        free += boss_here and not auth.read("g_CutsceneHasControl")
        if t % 30 == 0:
            for g in (a, g2):
                g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            for slot, (_, _, _, hp) in enemies(auth).items():
                if hp > 8:
                    auth.write("g_Entities", 8, "<h", slot * 0xBC + 0x3E)
                elif free > FIGHT_FREE:
                    auth.write("g_Entities", 0, "<h", slot * 0xBC + 0x3E)
                    flags = auth.read("g_Entities", "<I", slot * 0xBC + 0x34)
                    auth.write("g_Entities", flags | FLAG_DEAD, "<I", slot * 0xBC + 0x34)
        pads = (b["walk"], "") if not boss_here else (fight_pad(a, t=t), fight_pad(g2, t=t + 6))
        run.step(1, p1=pads)
        joint.tick()
        rush.tick()
    return until()


def row(name):
    return next(r for r in _bossstarts() if r["name"] == name)


@session_scenario()
def boss_rush_advances(run):
    """Slogra & Gaibon fall: the split is kept and, a few seconds on, both players are at the
    Doppleganger's start, its fight not yet won. Then both die: back at the Doppleganger's start
    (a retry, not the first boss)."""
    a, b = run.s.a, run.s.b
    rush, joint = rush_at(run, "Slogra & Gaibon")
    boss_flow(run, row("Slogra & Gaibon"))
    run.expect(drive(run, rush, joint, lambda: rush.state["index"] == 1, 600), "the rush moves on", state=rush.state)
    run.expect([s[0] for s in rush.state["splits"]] == ["Slogra & Gaibon"] and rush.state["splits"][0][1] > 0,
               "the split is kept", splits=rush.state["splits"])
    run.expect(at_start(run, rush, joint), "both are at the Doppleganger's start", a=a.snapshot(), b=b.snapshot())
    run.expect(not rush._beaten(), "his fight isn't won yet")
    for g in (a, b):  # both fall
        g.write("g_Status", 0, "<i", 0x23C)
    dead = lambda: all(g.mailbox("self_presence").flags & 16 for g in (a, b))
    drive(run, rush, joint, dead, 600)
    run.expect(drive(run, rush, joint, lambda: not dead() and all(
        g.mailbox("self_presence").flags & IN_PLAY and not g.mailbox("self_presence").flags & BUSY for g in (a, b)), 3000)
        and rush.state["index"] == 1, "both dead: the Doppleganger again (a retry)", state=rush.state)


@session_scenario()
def boss_rush_through_richter(run):
    """Richter: his death would start the ending; in a rush, a moment after he falls (before the
    ending's fade), both load into the Creature (the inverted castle's first)."""
    a, b = run.s.a, run.s.b
    rush, joint = rush_at(run, "Richter")
    run.expect(drive_fight(run, rush, joint, row("Richter"), lambda: rush.state["index"] == 12),
               "Richter falls", state=rush.state)
    run.expect(drive(run, rush, joint, lambda: rush.state["index"] == 12, 600), "the rush moves on to the Creature",
               state=rush.state)
    run.expect(at_start(run, rush, joint, 3600), "both are at the Creature's start, out of the ending",
               a=a.snapshot(), b=b.snapshot(), states=[g.read("g_GameState") for g in (a, b)])


@session_scenario()
def boss_rush_finishes(run):
    """Dracula, the last: his ending plays and the run is done, with its best time."""
    rush, joint = rush_at(run, "Dracula")
    boss_flow(run, row("Dracula"))
    run.expect(drive(run, rush, joint, lambda: rush.state.get("done"), 600), "the run is done", state=rush.state)
    run.expect(rush.state["best"] == rush.state["frames"] and "done" in rush.text(), "its time is the best",
               text=rush.text())
    run.expect(any(g.read("g_GameState") == GAME_ENDING for g in (run.s.a, run.s.b)), "Dracula's ending plays")


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
