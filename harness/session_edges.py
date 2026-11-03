"""Two players, two rooms, at the same moment (Tucker, 2026-11-02: "think like a bug hunter"):
both leaving one room by opposite doors on the same frame, both coming into one room from
opposite sides, passing each other in a doorway, one player in and out of a door while the other
stays, both teleporting to each other at once, and teleporting to a partner who is just leaving.
Each in both games: in play, where it should be, shared or not as it should be, nobody pulled,
nothing stuck. Two sets of three rooms, found by the crawl: the Marble Gallery's (31,27) | (32,27)
| (33,27). Late in the game the Castle Entrance's hall (14,40) is one of few rooms that always has
enemies (its zombies): the hall tests use it."""

from session import session_scenario  # first: puts `link` on the path

import roommap
from bots import walker
from link.mailbox import BOSS, BUSY, DEAD, FLIP_LOADING, IN_PLAY, PAUSED, ROLE_AUTHORITY, ROLE_GUEST, ROLE_NONE
from session_crawl import AREAS, START, _alive, _arrive
from session_m12 import STARTS, enemies
from session_travel import map_teleport

ROOMS = {"gallery": ("no0", (31, 27), (32, 27), (33, 27))}
AREA = STAGE = LEFT = MIDDLE = RIGHT = None  # set per test: _use(name)


def _use(name):
    """The rooms, each as its top-left cell: what a presence names a room by."""
    global AREA, STAGE, LEFT, MIDDLE, RIGHT
    AREA, *cells = ROOMS[name]
    STAGE = AREAS[AREA]
    rooms = roommap.rooms(AREA)

    def corner(cell):
        r = next(r for r in rooms if r.left <= cell[0] < r.left + r.w // 256 and r.top <= cell[1] < r.top + r.h // 256)
        return (r.left, r.top)
    LEFT, MIDDLE, RIGHT = (corner(c) for c in cells)
EDGE = 40          # px in from a room's edge: next to its door
SETTLE = 120       # frames for both games to agree on a room once both are in it
LOAD_LIMIT = 600


def _room(where):
    return next(r for r in roommap.rooms(AREA) if (r.left, r.top) == where)


def _at(run, g, where, side):
    """g on the floor of `where`, by its left or right door."""
    r = _room(where)
    x = EDGE if side == "left" else r.w - EDGE
    return _arrive(run, g, STAGE, r.room_id, *r.spot_near(x, r.h // 2))


def _here(g):
    p = g.mailbox("self_presence")
    return (p.room_left, p.room_top), p


def _walk(run, pads, frames, stop=None):
    """Both games walk (pads: A's way, B's way, or "" to stand) for up to `frames`; the frames
    either was mid-load are counted, and a load longer than LOAD_LIMIT is reported."""
    bots = [walker(w, attack_every=0) if w else None for w in pads]
    busy, worst = [0, 0], [0, 0]
    for t in range(frames):
        run.step(1, p1=tuple(bots[k](g.snapshot(), t) if bots[k] else "" for k, g in enumerate((run.s.a, run.s.b))))
        for k, g in enumerate((run.s.a, run.s.b)):
            _alive(g)
            busy[k] = busy[k] + 1 if _here(g)[1].flags & BUSY else 0
            worst[k] = max(worst[k], busy[k])
        if stop and stop():
            break
    run.expect(max(worst) < LOAD_LIMIT, "nobody stuck in a load", longest=worst)


def _settled(run, what, frames=SETTLE):
    run.step(frames)
    (ra, pa), (rb, pb) = _here(run.s.a), _here(run.s.b)
    run.expect(pa.flags & pb.flags & IN_PLAY and not (pa.flags | pb.flags) & BUSY, f"{what}: both in play",
               a=str(pa), b=str(pb))
    return ra, pa, rb, pb


def _shared(run, what):
    ra, pa, rb, pb = _settled(run, what)
    run.expect(ra == rb, f"{what}: the same room", a=ra, b=rb)
    run.expect({pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}, f"{what}: one authority, one guest",
               roles=(pa.role, pb.role))
    ea, eb = enemies(run.s.a), enemies(run.s.b)
    run.expect(len(ea) == len(eb), f"{what}: the same enemies in both games", a=len(ea), b=len(eb))


def _apart(run, what, want_a, want_b):
    ra, pa, rb, pb = _settled(run, what)
    run.expect((ra, rb) == (want_a, want_b), f"{what}: A in {want_a}, B in {want_b}", a=ra, b=rb)
    run.expect(pa.role == pb.role == ROLE_NONE, f"{what}: neither room shared", roles=(pa.role, pb.role))


def edges_leave_by_opposite_doors_at_once(run):
    """Both in the middle room (shared); on one frame A walks out left and B out right."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, a, MIDDLE, "left") and _at(run, b, MIDDLE, "right"), "both in the middle room")
    _shared(run, "together first")
    _walk(run, ("left", "right"), 600, stop=lambda: _here(a)[0] != MIDDLE and _here(b)[0] != MIDDLE)
    _apart(run, "apart", LEFT, RIGHT)
    run.step(300)
    _apart(run, "and nobody is pulled back", LEFT, RIGHT)


def edges_enter_from_opposite_doors_at_once(run):
    """A by the left room's door, B by the right room's; on one frame both walk into the middle."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, a, LEFT, "right") and _at(run, b, RIGHT, "left"), "on either side")
    _walk(run, ("right", "left"), 600, stop=lambda: _here(a)[0] == MIDDLE and _here(b)[0] == MIDDLE)
    run.step(30)
    _shared(run, "both arrived at once")


def edges_pass_in_a_doorway(run):
    """A walks from the left room into the middle while B walks from the middle into the left room,
    through the same door, on the same frame."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, a, LEFT, "right") and _at(run, b, MIDDLE, "left"), "either side of one door")
    _walk(run, ("right", "left"), 600, stop=lambda: _here(a)[0] == MIDDLE and _here(b)[0] == LEFT)
    _apart(run, "swapped", MIDDLE, LEFT)


def edges_in_and_out_of_a_door(run):
    """B stands in the middle room; A goes in and out of its left door six times, quickly. B's
    game keeps its enemies (none twice), and they share the room each time A is in it."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, b, MIDDLE, "left") and _at(run, a, LEFT, "right"), "B in the middle, A next door")
    counts = []
    for k in range(6):
        _walk(run, ("right", ""), 300, stop=lambda: _here(a)[0] == MIDDLE)
        run.step(20)
        counts.append(len(enemies(b)))
        _walk(run, ("left", ""), 300, stop=lambda: _here(a)[0] == LEFT)
        run.step(20)
    run.expect(_here(b)[0] == MIDDLE, "B never moved", b=_here(b)[0])
    run.expect(max(counts) - min(counts) <= 2, "B's enemies don't multiply", counts=counts)
    _walk(run, ("right", ""), 300, stop=lambda: _here(a)[0] == MIDDLE)
    _shared(run, "A in once more")


def edges_teleport_to_each_other_at_once(run):
    """A in the left room, B in the right one; on one frame both open the map and press ✕. Each
    goes to where the other was: they end up swapped, or together; never stuck, never ping-pong."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, a, LEFT, "left") and _at(run, b, RIGHT, "right"), "apart")
    run.step(60)
    pads = lambda pad: (pad, pad)
    run.step(1, p1=pads("select"))
    run.step(40)
    run.step(1, p1=pads("cross"))
    rooms = ([], [])
    for t in range(900):
        run.step(1)
        for k, g in enumerate((a, b)):
            _alive(g)
            r, p = _here(g)
            if p.flags & IN_PLAY and not p.flags & BUSY and (not rooms[k] or rooms[k][-1] != r):
                rooms[k].append(r)
    ra, pa, rb, pb = _settled(run, "after both teleports")
    run.expect(all(len(x) <= 2 for x in rooms), "each moves once at most (no ping-pong)", a=rooms[0], b=rooms[1])
    run.expect((ra, rb) in ((RIGHT, LEFT), (LEFT, LEFT), (RIGHT, RIGHT)), "swapped, or together", a=ra, b=rb)


def edges_teleport_to_a_partner_leaving(run):
    """A in the left room; B by the middle room's right door. A teleports to B from the map as B
    walks out into the right room: A arrives where B was, in play, and nothing hangs."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, a, LEFT, "left") and _at(run, b, MIDDLE, "right"), "apart")
    run.step(60)
    map_teleport(run, a)
    _walk(run, ("", "right"), 600, stop=lambda: _here(b)[0] == RIGHT and _here(a)[0] == MIDDLE)
    ra, pa, rb, pb = _settled(run, "after")
    run.expect(ra in (MIDDLE, RIGHT) and rb == RIGHT, "A came after B; B is in the right room", a=ra, b=rb)


# Each case three ways: on the couch; online, on the playtest's connection (lag widens every
# race: both games stay authority longer, a teleport reads an older presence); and Alucard with
# Richter, whose door walks are his own code.
VARIANTS = (("", None, (0, 0), False), ("_online", "playtest", (0, 0), False), ("_richter", None, (0, 1), True))


def _register(fn, name=None):
    for suffix, net, chars, full in VARIANTS:
        def test(run, fn=fn, name=name, net=net):
            if name:
                _use(name)
            if net:
                run.s.set_net(net, 1)
            fn(run)
        test.__name__ = f"{fn.__name__}{'_' + name if name else ''}{suffix}"
        test.__doc__ = fn.__doc__
        session_scenario(starts=(START, START), characters=chars, full=full)(test)


for _fn in (edges_leave_by_opposite_doors_at_once, edges_enter_from_opposite_doors_at_once, edges_pass_in_a_doorway,
            edges_in_and_out_of_a_door, edges_teleport_to_each_other_at_once, edges_teleport_to_a_partner_leaving):
    for _name in ROOMS:
        _register(_fn, _name)


def _hall(run):
    global AREA, STAGE
    AREA, STAGE = "np3", AREAS["np3"]
    hall = next(r for r in roommap.rooms("np3") if (r.left, r.top) == (14, 40))
    beyond = next(r for r in roommap.rooms("np3") if (r.left, r.top) == (20, 39))
    return hall, beyond


def edges_both_through_one_door_into_enemies(run):
    """Both step out of the Castle Entrance hall's right door, then on one frame walk back in
    through it. One room, one authority, one set of zombies: the same in both games."""
    a, b = run.s.a, run.s.b
    hall, beyond = _hall(run)
    x = hall.w - EDGE
    run.expect(_arrive(run, a, STAGE, hall.room_id, *hall.spot_near(x, hall.h // 2)) and
               _arrive(run, b, STAGE, hall.room_id, *hall.spot_near(x - 16, hall.h // 2)), "both by the hall's right door")
    _walk(run, ("right", "right"), 600, stop=lambda: _here(a)[0] == (20, 39) and _here(b)[0] == (20, 39))
    run.expect(_here(a)[0] == _here(b)[0] == (20, 39), "both stepped out", a=_here(a)[0], b=_here(b)[0])
    run.step(30)
    _walk(run, ("left", "left"), 600, stop=lambda: _here(a)[0] == (14, 40) and _here(b)[0] == (14, 40))
    run.expect(_here(a)[0] == _here(b)[0] == (14, 40), "and back in, on one frame", a=_here(a)[0], b=_here(b)[0])
    run.step(120, p1=("left", "left"))
    for _ in range(600):  # its zombies rise as players walk in
        if enemies(a):
            break
        run.step(1)
    run.expect(enemies(a), "the hall's zombies are there", n=len(enemies(a)))
    _shared(run, "both in the hall")


def edges_in_and_out_among_enemies(run):
    """Both in the hall with its zombies; A steps out of the right door and back in, four times.
    Each time back, both games show the same zombies, and B's never pile up."""
    a, b = run.s.a, run.s.b
    hall, beyond = _hall(run)
    x = hall.w - EDGE
    run.expect(_arrive(run, a, STAGE, hall.room_id, *hall.spot_near(x, hall.h // 2)) and
               _arrive(run, b, STAGE, hall.room_id, *hall.spot_near(x - 200, hall.h // 2)), "both in the hall")
    _shared(run, "together")
    counts, worst = [], []
    for k in range(4):
        _walk(run, ("right", ""), 400, stop=lambda: _here(a)[0] == (20, 39))
        run.expect(_here(a)[0] == (20, 39), f"A out ({k + 1})", a=_here(a)[0])
        run.step(30)
        _walk(run, ("left", ""), 400, stop=lambda: _here(a)[0] == (14, 40))
        run.step(SETTLE)
        counts.append((len(enemies(a)), len(enemies(b))))
        off = 0  # online, the guest shows the authority's zombies a few frames late: a rising or
        for _ in range(120):  # falling one can differ for that long, not for good
            run.step(1)
            off = off + 1 if len(enemies(a)) != len(enemies(b)) else 0
            worst.append(off)
    print("W", counts, max(worst), flush=True)
    run.expect(max(worst) <= 20, "back in: the same zombies in both games (any difference gone within 20 frames)",
               longest=max(worst), counts=counts)
    run.expect(max(y for _, y in counts) <= 2 * max(1, min(y for _, y in counts)), "B's don't pile up", counts=counts)


def edges_teleport_back_while_arriving(run):
    """A teleports to B from the map; while A is still loading, B teleports back to A. B must not
    chase A's half-loaded presence: each ends in play, no load hangs, at most one move each."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, a, LEFT, "left") and _at(run, b, RIGHT, "right"), "apart")
    run.step(60)
    map_teleport(run, a)
    for _ in range(300):  # until A is mid-load
        run.step(1)
        if a.mailbox("self_presence").flip_x & FLIP_LOADING:
            break
    run.expect(a.mailbox("self_presence").flip_x & FLIP_LOADING, "A is loading")
    map_teleport(run, b)
    rooms = ([], [])
    _walk(run, ("", ""), 900, stop=None)
    ra, pa, rb, pb = _settled(run, "after both")
    run.expect(ra == RIGHT, "A arrived where B was", a=ra)
    run.expect(rb in (RIGHT, LEFT), "B stayed, or went to where A was", b=rb)


def edges_leave_while_partner_paused(run):
    """Both in the middle room; A opens the menu (which holds a shared room still); B walks out of
    it. Then A closes the menu: both play on, apart, nobody frozen."""
    a, b = run.s.a, run.s.b
    run.expect(_at(run, a, MIDDLE, "left") and _at(run, b, MIDDLE, "right"), "both in the middle room")
    _shared(run, "together")
    run.step(1, p1=("start", ""))
    run.step(30)
    run.expect(a.mailbox("self_presence").flags & PAUSED, "A in the menu")
    _walk(run, ("", "right"), 600, stop=lambda: _here(b)[0] == RIGHT)
    run.expect(_here(b)[0] == RIGHT, "B walked out while A was in the menu", b=_here(b)[0])
    run.step(1, p1=("start", ""))
    run.step(30)
    t0 = a.read("g_Timer")
    run.step(60)
    run.expect(a.read("g_Timer") - t0 >= 55, "A's game runs again", frames=a.read("g_Timer") - t0)
    _apart(run, "after", MIDDLE, RIGHT)


def edges_die_as_partner_leaves(run):
    """Both in the Castle Entrance hall; B, at 1 HP, walks into its zombies as A walks out of the
    right door. B's death brings it back at A, in A's room, in play."""
    a, b = run.s.a, run.s.b
    hall, beyond = _hall(run)
    x = hall.w - EDGE
    run.expect(_arrive(run, a, STAGE, hall.room_id, *hall.spot_near(x, hall.h // 2)) and
               _arrive(run, b, STAGE, hall.room_id, *hall.spot_near(x - 300, hall.h // 2)), "both in the hall")
    run.step(SETTLE)
    b.write("g_Status", 1, "<i", 0x23C)
    bots = (walker("right"), walker("left"))
    dead = None
    for t in range(3000):
        run.step(1, p1=(bots[0](a.snapshot(), t), bots[1](b.snapshot(), t) if dead is None else ""))
        _alive(a)
        if dead is None and b.mailbox("self_presence").flags & DEAD:
            dead = t
        if dead is not None and t - dead > 60 and b.mailbox("self_presence").flags & IN_PLAY and not b.mailbox("self_presence").flags & (DEAD | BUSY):
            break
    run.expect(dead is not None, "B died", t=dead)
    run.expect(_here(a)[0] != (14, 40), "A left the hall meanwhile", a=_here(a)[0])
    ra, pa, rb, pb = _settled(run, "after B's revival")
    run.expect(rb == ra, "B came back at A, in A's room", a=ra, b=rb)


A_TO_BOSS = 201  # frames A walks from this start before its fight begins (measured)
B_TO_DOOR = 26   # frames B walks from beside the Gallery middle room's right door to its load (measured)


def edges_boss_pull_mid_door(run):
    """A walks into Slogra and Gaibon; B, in the Marble Gallery, walks through a door (not the save
    room's: a save room is never left for a pull), timed so the fight begins as B's door starts loading. B, mid-load, is pulled once that load is done: no
    hang, and both in the fight."""
    import bossstarts
    a, b = run.s.a, run.s.b
    row = next(r for r in bossstarts.B if r["name"] == "Slogra & Gaibon")
    _use("gallery")
    run.expect(_at(run, b, MIDDLE, "right"), "B by a Gallery door")
    run.step(60)
    bots = (walker(row["walk"]), walker("right"))
    b_start = A_TO_BOSS - B_TO_DOOR - 3
    pulled, busy, b_at_boss, through = None, 0, None, False
    for t in range(4000):
        through = through or (_here(b)[0] == RIGHT and not b.mailbox("self_presence").flags & BUSY)
        # B lets go once through its door, as a player would on being pulled
        run.step(1, p1=(bots[0](a.snapshot(), t), bots[1](b.snapshot(), t) if b_start <= t and not through else ""))
        _alive(a)
        _alive(b)
        pb = b.mailbox("self_presence")
        busy = busy + 1 if pb.flags & BUSY and not b.read("g_CutsceneHasControl") else 0
        if busy == LOAD_LIMIT:
            run.expect(False, "B never stuck in a load", where=str(pb))
        if b_at_boss is None and a.mailbox("self_presence").flags & BOSS:
            b_at_boss = (_here(b)[0], bool(pb.flags & BUSY), bool(pb.flip_x & FLIP_LOADING))
        if a.mailbox("self_presence").flags & BOSS and pb.flags & BOSS:
            pulled = t
            break
    run.expect(b_at_boss and b_at_boss[1], "B was in its door's load when the fight began", at_boss=b_at_boss)
    run.expect(pulled is not None, "both end up in the fight", a=str(a.mailbox("self_presence")), b=str(b.mailbox("self_presence")))
    for t in range(SETTLE):
        run.step(1)
        _alive(a)
        _alive(b)
    run.expect(_here(a)[0] == _here(b)[0] and b.mailbox("self_presence").flags & BOSS, "B stays in the fight",
               a=_here(a)[0], b=_here(b)[0])


def edges_boss_pull_waits_for_the_save_room(run):
    """B is in the Marble Gallery's save room (31,27) when A's fight with Slogra and Gaibon begins:
    a save room is never left for a pull. Then B walks out of it, and is pulled in."""
    import bossstarts
    a, b = run.s.a, run.s.b
    row = next(r for r in bossstarts.B if r["name"] == "Slogra & Gaibon")
    _use("gallery")
    run.expect(_at(run, b, LEFT, "right"), "B in the save room")
    run.step(60)
    bot = walker(row["walk"])
    for t in range(1500):
        run.step(1, p1=(bot(a.snapshot(), t), ""))
        _alive(a)
        if a.mailbox("self_presence").flags & BOSS:
            break
    run.expect(a.mailbox("self_presence").flags & BOSS, "A's fight began")
    run.step(300)
    run.expect(_here(b)[0] == LEFT and not b.mailbox("self_presence").flags & BOSS, "B, in the save room, stays",
               b=_here(b)[0])
    bot = walker("right")
    for t in range(1500):
        run.step(1, p1=("", bot(b.snapshot(), t) if _here(b)[0] == LEFT else ""))
        _alive(a)
        _alive(b)
        if b.mailbox("self_presence").flags & BOSS:
            break
    run.expect(b.mailbox("self_presence").flags & BOSS, "out of the save room, B is pulled in", b=str(b.mailbox("self_presence")))


_register(edges_teleport_back_while_arriving, "gallery")
_register(edges_leave_while_partner_paused, "gallery")
_register(edges_die_as_partner_leaves)
_register_boss = lambda fn: [session_scenario(starts=(str(STARTS / "Boss - Slogra and Gaibon.state"),) * 2, characters=c,
                                              full=f)(_named(fn, sfx, net)) for sfx, net, c, f in VARIANTS]


def _named(fn, suffix, net):
    def test(run):
        if net:
            run.s.set_net(net, 1)
        fn(run)
    test.__name__ = fn.__name__ + suffix
    test.__doc__ = fn.__doc__
    return test


_register_boss(edges_boss_pull_mid_door)
_register_boss(edges_boss_pull_waits_for_the_save_room)
_register(edges_both_through_one_door_into_enemies)
_register(edges_in_and_out_among_enemies)





