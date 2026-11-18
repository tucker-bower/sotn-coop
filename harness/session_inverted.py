"""The inverted castle, together (v1.1, D114): travel between the two castles and what the partners
share there. Its bosses are in session_m12 (boss_* from bossstarts.INVERTED)."""

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


ENDING_KIND = 0x800978B4  # D_800978B4: which ending the game plays


TRIO_FALLEN = 0x801806B4  # RBO0's D_us_801806B4: the fakes fallen; at 3 the fight ends (e_boss.c)


def _kill(g, slot):
    from session_m12 import FLAG_DEAD
    g.write("g_Entities", 0, "<h", slot * 0xBC + 0x3E)
    g.write("g_Entities", g.read("g_Entities", "<I", slot * 0xBC + 0x34) | FLAG_DEAD, "<I", slot * 0xBC + 0x34)


def _authority_changes(name, test_name, full):
    """Issue 248: a boss fight whose state is in its overlay's .data (a variable given a starting
    value), which a shared room's guest didn't get from the authority: the fake trio's count of
    fallen fakes (at 3 the fight ends), Karasuman's and Darkwing Bat's door lock. The fight starts
    in one game's room; part of it is won there (one fake falls, or the boss is worn down); then
    that player steps out of the arena and back, so the room passes to the other game, where the
    rest falls. The fight ends in both games (the inverted castle's: with its record)."""
    def test(run):
        import bossstarts
        from link.mailbox import BOSS, CMD_ARRIVE, ROLE_AUTHORITY
        from session_m12 import SceneWatch, enemies, fight_pad
        a, b = run.s.a, run.s.b
        row = next(r for r in bossstarts.B if r["name"] == name)
        walk, stage = row["walk"], bossstarts.STAGES[row["stage"]]
        trio = name.startswith("Fake")
        w = SceneWatch(run)
        boss = lambda g: g.mailbox("self_presence").flags & BOSS
        auth = lambda: next((g for g in (a, b) if g.mailbox("self_presence").role == ROLE_AUTHORITY), None)

        def alive(*_):
            for g in (a, b):
                g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            return ("", "")
        event = bossstarts.EVENTS.get(row.get("event")) if row.get("inverted") else None
        w.until(lambda: boss(a), 4000, lambda i: (walk + ("+cross" if i % 90 < 12 else ""), ""))
        w.until(lambda: boss(b), 3000, ("", walk))
        if event is not None:  # both into the arena, where the fight's manager starts it (its visited bit)
            near = lambda g: fight_pad(g).replace("+square", "").replace("square", "")  # toward the boss
            w.until(lambda: a.read("g_Settings", "<I", 0x108) & (1 << event), 900, lambda i: (walk, "") if trio else (near(a), near(b)))  # (the trio's starts at x 224-320)
            run.expect(a.read("g_Settings", "<I", 0x108) & (1 << event), "the fight has started", a=a.snapshot())
        run.expect(boss(a) and boss(b), "both are in the fight", a=a.snapshot(), b=b.snapshot())
        w.step(300, alive)
        w.until(lambda: auth() is not None, 1200, alive)  # (after the boss's entrance scene)
        first = auth()
        run.expect(first is not None, "one game runs the room")
        foes = {s: v for s, v in enemies(first).items() if v[3] > 50}
        run.expect(len(foes) >= (3 if trio else 1), "the boss is there", foes=enemies(first))
        if trio:
            _kill(first, min(foes))
            w.until(lambda: first.read(TRIO_FALLEN, "<i") >= 1, 600, alive)
            run.expect(first.read(TRIO_FALLEN, "<i") == 1, "one fake falls in the authority's game")
        else:
            for s in foes:
                first.write("g_Entities", 8, "<h", s * 0xBC + 0x3E)  # worn down
            w.step(60, alive)
        other = b if first is a else a
        first.mailbox("command", CMD_ARRIVE, stage, *row["arrive"])  # out of the arena...
        w.until(lambda: other.mailbox("self_presence").role == ROLE_AUTHORITY, 600, alive)
        w.step(120, alive)
        pads = (walk, "") if first is a else ("", walk)
        w.until(lambda: boss(first), 900, lambda i: (alive(), pads)[1])  # ...and back in
        w.step(120, alive)
        run.expect(auth() is other, "the room passed to the other game",
                   roles=[g.mailbox("self_presence").role for g in (a, b)])
        for s in sorted(s for s, v in enemies(other).items() if v[3] > 0):
            _kill(other, s)
        done = lambda: not boss(a) and not boss(b)
        k = bossstarts.RECORDS + 4 * event if event is not None else None
        if k is not None:
            done = lambda: all(g.read("g_Settings", "<i", k) for g in (a, b))
        w.until(done, 1800, alive)
        run.expect(done(), "the fight ends in both games" + (", with its record" if k is not None else ""),
                   fallen=[g.read(TRIO_FALLEN, "<i") for g in (a, b)] if trio else None,
                   boss=[bool(boss(g)) for g in (a, b)], left=[sorted(enemies(g).values())[:4] for g in (a, b)],
                   records=[g.read("g_Settings", "<i", k) for g in (a, b)] if k is not None else None,
                   steps=[[(i, g.read("g_Entities", "<H", i * 0xBC + 0x26), g.read("g_Entities", "<H", i * 0xBC + 0x2C))
                           for i in range(64, 96) if g.read("g_Entities", "<H", i * 0xBC + 0x26)] for g in (a, b)],
                   xa=[g.read(0x8013901C, "<h") for g in (a, b)])
    test.__name__ = test_name
    test.__doc__ = _authority_changes.__doc__
    session_scenario(starts=(str(STARTS / f"Boss - {name.replace(' & ', ' and ')}.state"),) * 2, full=full)(test)


_authority_changes("Fake Trevor, Grant & Sypha", "boss_trio_authority_changes", False)
_authority_changes("Darkwing Bat", "boss_darkwing_bat_authority_changes", False)
_authority_changes("Karasuman", "boss_karasuman_authority_changes", True)


@session_scenario(starts=(str(STARTS / "Boss - Fake Trevor, Grant and Sypha.state"),) * 2, characters=(0, 1))
def boss_trio_partner_locked_out(run):
    """Issue 248: B waits at the fake trio's door while A walks in and starts the fight; the arena's
    door closes with B outside, where its way out loads the arena again at the door. B walks at
    the door, then waits: within some seconds B is put beside A, and A is never pulled out of the
    fight after B (the chain lost the fight this way: B, just out of the arena's stage, still
    showed its boss for a frame, and A followed)."""
    import bossstarts
    from link.mailbox import BOSS
    from session_m12 import SceneWatch
    a, b = run.s.a, run.s.b
    row = next(r for r in bossstarts.B if r["name"].startswith("Fake"))
    walk, arena = row["walk"], []
    w = SceneWatch(run)
    boss = lambda g: g.mailbox("self_presence").flags & BOSS
    where = lambda g: g.mailbox("self_presence")
    left_fight = []

    def alive(pads):
        def f(*_):
            for g in (a, b):
                g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            pa = where(a)
            if pa.stage != arena[0] and not left_fight:
                left_fight.append((w.t, pa.stage, a.snapshot()))
            return pads
        return f
    w.until(lambda: boss(a), 4000, lambda i: (walk + ("+cross" if i % 90 < 12 else ""), ""))
    w.until(lambda: boss(b), 3000, ("", ""))
    event = bossstarts.EVENTS[row["event"]]
    w.until(lambda: a.read("g_Settings", "<I", 0x108) & (1 << event), 900, (walk, ""))
    run.expect(a.read("g_Settings", "<I", 0x108) & (1 << event), "A starts the fight", a=a.snapshot(), b=b.snapshot())
    arena.append(where(a).stage)  # RBO0: the arena's own stage
    w.step(300, alive(("", walk)))  # B walks at the closed door, then waits
    inside = lambda: where(b).stage == arena[0] and b.snapshot()["world_x"] > 80 and boss(b)  # (the door: x 64-80)
    w.until(inside, 900, alive(("", "")))
    run.expect(inside(), "B is put beside A, past the door", b=b.snapshot(), a=a.snapshot(), b_flags=where(b).flags)
    run.expect(not left_fight, "A never leaves the fight", left=left_fight[:1])
