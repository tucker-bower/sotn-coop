"""The inverted castle, together (v1.1, D114): travel between the two castles and what the partners
share there. Its bosses are in session_m12 (m12_boss_* from bossstarts.INVERTED)."""

from session import session_scenario  # first: puts `link` on the path

from session_m12 import STARTS
from session_progress import arrive
from session_travel import map_teleport, wait_arrived

START = str(STARTS / "Boss - Richter.state")  # late in the first castle: at Richter's door (BO6)
RNO0, NO0 = 0x20, 0x00
WIDE = 48     # RNO0's room 48: four screens wide, one tall (assets/st/rno0/rooms.json)
SPOT = (700, 120)  # in it, as the player sees it: past where a mirrored arrival lands (1024 - 700)
GALLERY = (80, 728, 135)  # NO0: next to Maria (debugstarts)


def _settle(run, g):
    """A moment for g to land on the floor below where it arrived."""
    run.step(120)
    return g.mailbox("self_presence")


def _near(p, target):
    return p.room == target.room and abs(p.x - target.ground_x) <= 16 and abs(p.y - target.ground_y) <= 16


@session_scenario(starts=(START, START))
def inverted_teleport_into(run):
    """A is in the inverted castle (the Black Marble Gallery's wide room), B in the first castle
    (the Marble Gallery). B opens the map and presses ✕: it lands next to A, in the inverted
    castle. Before, the game read the target stage twice and the second read turned it into the
    first castle's (NO0 for RNO0), and an arrival from another stage landed mirrored."""
    a, b = run.s.a, run.s.b
    arrive(run, a, RNO0, WIDE, *SPOT)
    arrive(run, b, NO0, *GALLERY)
    target = _settle(run, a)
    run.expect(target.stage == RNO0 and abs(target.x - SPOT[0]) <= 16, "A arrived where it was sent (not mirrored)",
               a=str(target))
    map_teleport(run, b)
    frames = wait_arrived(run, b, target)
    q = _settle(run, b)
    run.expect(frames is not None and q.stage == RNO0, "B is in the inverted castle", b=str(q), frames=frames)
    run.expect(_near(q, target), "next to A", b=str(q), a=str(target))


@session_scenario(starts=(START, START))
def inverted_teleport_out(run):
    """The other way: A, in the inverted castle, opens the map and presses ✕ to B in the first
    castle's Marble Gallery, and lands next to B there."""
    a, b = run.s.a, run.s.b
    arrive(run, a, RNO0, WIDE, *SPOT)
    arrive(run, b, NO0, *GALLERY)
    target = _settle(run, b)
    _settle(run, a)
    map_teleport(run, a)
    frames = wait_arrived(run, a, target)
    q = _settle(run, a)
    run.expect(frames is not None and q.stage == NO0, "A is in the first castle", a=str(q), frames=frames)
    run.expect(_near(q, target), "next to B", a=str(q), b=str(target))


@session_scenario(starts=(START, START))
def inverted_map_shared(run):
    """What A explores in the inverted castle shows on B's map (the inverted map is g_CastleMap's
    second half: progress.c's EV_MAP), while B is in the first castle."""
    a, b = run.s.a, run.s.b
    arrive(run, b, NO0, *GALLERY)
    inv = lambda g: g.read_bytes("g_CastleMap", 0x400, 0x400)
    before = inv(a)
    arrive(run, a, RNO0, WIDE, *SPOT)
    run.step(180)
    new = [(i, x & ~y) for i, (x, y) in enumerate(zip(inv(a), before)) if x & ~y]
    theirs = inv(b)
    run.expect(new, "A's inverted map has new rooms")
    run.expect(all(theirs[i] & bits == bits for i, bits in new), "B's map has them too",
               new=new[:6], b=[theirs[i] for i, _ in new[:6]])


ENDING_KIND = 0x800978B4  # D_800978B4: which ending the game plays


def _final_boss_elsewhere(name, start, limit):
    """A kills the final boss alone; B is in another area with its menu open (so no pull brings
    it in). B's game still follows A's into the ending, the same one (boss.c's EV_KILLED)."""
    def test(run):
        from session_m12 import FIGHT_FREE, GAME_ENDING, GAME_TITLE, boss_alone
        a, b = run.s.a, run.s.b
        arrive(run, b, NO0, *GALLERY)
        run.step(60)
        run.step(1, p1=("", "start"))  # B's menu: paused, so it can't be pulled into the fight
        run.step(60)
        boss_alone(run, a, name)
        ended = [None, None]
        for t in range(limit):
            for k, g in enumerate((a, b)):
                if ended[k] is None and g.read("g_GameState") in (GAME_ENDING, GAME_TITLE):
                    ended[k] = t
                if ended[k] is None:
                    g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            if None not in ended:
                break
            run.step(1)
        run.expect(ended[0] is not None, f"killing {name} ends A's game", ended=ended)
        run.expect(ended[1] is not None, "B, elsewhere in its menu, follows into the ending", ended=ended,
                   b=b.snapshot(), state=b.read("g_GameState"))
        kinds = [g.read(ENDING_KIND) for g in (a, b)]
        run.expect(kinds[0] == kinds[1], "the same ending", kinds=kinds)
    test.__name__ = f"final_boss_elsewhere_{name.lower()}"
    test.__doc__ = _final_boss_elsewhere.__doc__.replace("the final boss", name)
    session_scenario(starts=(start, start))(test)


_final_boss_elsewhere("Richter", START, 3000)
_final_boss_elsewhere("Dracula", str(STARTS / "Boss - Dracula.state"), 6000)
