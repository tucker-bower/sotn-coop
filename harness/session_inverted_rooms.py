"""The inverted castle, room by room, with both players (issue 47; Tucker, 2026-11-02: "going between
rooms, opening doors, entering bossfights"). Starts are bossstarts.INVERTED's, outside each boss.

- inverted_rooms_<area>: both walk away from the boss's door, through a door, together. B
  follows A into each room, neither bounces back through a door, both stay in play, and a room
  they share has one authority and one guest.
- inverted_boss_walk_in_<boss>: both walk through the boss's door at once (the pull-in tests have
  B pulled; this is the race of both arriving), and both end up in one fight that stays shared
  and doesn't restart.

Health is topped up every frame: the walk is the test, not the enemies on the way."""

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from link.mailbox import BOSS, BUSY, DEAD, IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST
from session_m12 import STARTS

HP, HP_MAX = 0x23C, 0x240  # g_Status
BOUNCE_FRAMES = 120   # back into the room just left this soon: bounced off the door
FOLLOW_FRAMES = 600   # B, a step behind A, reaches A's room within this
SETTLE_FRAMES = 30    # arriving on the same frame, both games are authority until they hear each other


# Where a walking bot can't get through the next door (a ledge it can't jump, enemies that knock it
# back): those areas have their boss walk-in only.
NO_WALK = {"RNO2", "RARE", "RDAI"}


def _rows():
    import bossstarts
    return [r for r in bossstarts.INVERTED if not r.get("out") and not r.get("check")]


def _alive(g):
    g.write("g_Status", g.read("g_Status", "<i", HP_MAX), "<i", HP)


def _where(g):
    p = g.mailbox("self_presence")
    return (p.stage, p.room_left, p.room_top), p


def travel(run, way, rooms_needed=1, limit=3600):
    """Both walk `way` (B starting a moment later) until A has been through rooms_needed doors."""
    a, b = run.s.a, run.s.b
    bots = (walker(way, attack_every=24), walker(way, attack_every=24))
    seen = ([], [])        # each game's rooms, in order, with the frame it entered
    for t in range(limit):
        pads = tuple(bots[k](g.snapshot(), t) if t >= 20 * k else "" for k, g in enumerate((a, b)))
        run.step(1, p1=pads)
        for k, g in enumerate((a, b)):
            _alive(g)
            room, p = _where(g)
            if p.flags & IN_PLAY and not p.flags & BUSY and (not seen[k] or seen[k][-1][0] != room):
                seen[k].append((room, t))
        if len(seen[0]) > rooms_needed and len(seen[1]) >= len(seen[0]):
            break
    rooms = [[r for r, _ in s] for s in seen]
    run.expect(len(rooms[0]) > rooms_needed, f"A goes through {rooms_needed} doors", a=rooms[0])
    run.expect(rooms[1][:len(rooms[0])] == rooms[0], "B follows A into the same rooms, in order", a=rooms[0], b=rooms[1])
    for k, s in enumerate(seen):
        bounces = [(s[i][0], s[i + 1][1] - s[i][1]) for i in range(1, len(s) - 1)
                   if s[i + 1][0] == s[i - 1][0] and s[i + 1][1] - s[i][1] < BOUNCE_FRAMES]
        run.expect(not bounces, f"{'AB'[k]} never bounces back through a door", bounces=bounces)
    for i, (room, at) in enumerate(seen[0][1:], 1):
        later = next((t for r, t in seen[1] if r == room), None)
        run.expect(later is not None and later - at <= FOLLOW_FRAMES, f"B reaches room {i} soon after A",
                   room=room, a_at=at, b_at=later)
    run.step(120)
    pa, pb = (_where(g)[1] for g in (a, b))
    run.expect(pa.flags & pb.flags & IN_PLAY and not (pa.flags | pb.flags) & DEAD, "both in play at the end",
               a=str(pa), b=str(pb))
    if _where(a)[0] == _where(b)[0]:
        run.expect({pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}, "the room they share: one authority, one guest",
                   roles=(pa.role, pb.role))


def walk_in(run, way, limit=4000, hold=600):
    """Both walk through the boss's door at once: both in one fight that stays one."""
    a, b = run.s.a, run.s.b
    bots = (walker(way), walker(way))
    boss = lambda g: g.mailbox("self_presence").flags & BOSS
    for t in range(limit):
        run.step(1, p1=tuple(bots[k](g.snapshot(), t) for k, g in enumerate((a, b))))
        for g in (a, b):
            _alive(g)
        if boss(a) and boss(b):
            break
    run.expect(boss(a) and boss(b), "both are in the boss fight", a=str(_where(a)[1]), b=str(_where(b)[1]))
    busy, lost, roles, settling, scene = 0, 0, set(), 0, 0
    for t in range(hold):
        run.step(1)
        for g in (a, b):
            _alive(g)
        pa, pb = (_where(g)[1] for g in (a, b))
        scene += bool(a.read("g_CutsceneHasControl") and b.read("g_CutsceneHasControl"))
        busy += bool((pa.flags | pb.flags) & BUSY) and not (a.read("g_CutsceneHasControl") or b.read("g_CutsceneHasControl"))
        lost += not (pa.flags & pb.flags & BOSS)
        if _where(a)[0] == _where(b)[0] and not (pa.flags | pb.flags) & BUSY:
            if {pa.role, pb.role} != {ROLE_AUTHORITY, ROLE_GUEST} and t < SETTLE_FRAMES:
                settling += 1
            else:
                roles.add((pa.role, pb.role))
    run.expect(lost == 0, "the fight stays on for both (no restart, nobody out of it)", frames_out=lost)
    run.expect(busy < 60, "nobody is sent through a load again", busy_frames=busy)
    if not roles:  # a fight that opens with a long scene (Death's): both in it together
        run.expect(scene > hold * 0.9, "both are in the fight's opening scene together", scene_frames=scene)
        return
    run.expect(all({x, y} == {ROLE_AUTHORITY, ROLE_GUEST} for x, y in roles),
               f"one fight: one authority, one guest (after {settling} frames of the two hearing each other)",
               roles=sorted(roles))


def _register(row, everyday):
    name = row["name"].replace(" & ", " and ")
    start = str(STARTS / f"Boss - {name}.state")
    slug = name.lower().replace(",", "").replace(" ", "_")
    back = {"left": "right", "right": "left"}[row["walk"]]

    def rooms(run):
        travel(run, back)
    rooms.__name__ = f"inverted_rooms_{row['stage'].lower()}"
    rooms.__doc__ = f"{row['area']}: both players walk away from {row['name']}'s door, through the next door, together."
    if row["stage"] not in NO_WALK:
        session_scenario(starts=(start, start), full=not everyday)(rooms)

    def boss(run):
        walk_in(run, row["walk"])
    boss.__name__ = f"inverted_boss_walk_in_{slug}"
    boss.__doc__ = f"Both players walk into {row['name']} ({row['area']}) at the same moment."
    session_scenario(starts=(start, start), full=not everyday)(boss)


for _k, _row in enumerate(_rows()):
    _register(_row, everyday=_k < 2)
