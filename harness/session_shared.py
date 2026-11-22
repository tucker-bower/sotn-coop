"""M4 acceptance tests: shared rooms, the same enemies (design/M4-shared-rooms.md).

The stage is the castle entrance hall (NO3 room 14,40), which has zombies. A walks in first
(the authority); B arrives at A's spot afterwards (the guest)."""

import struct

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from link.mailbox import ROLE_AUTHORITY, ROLE_GUEST, ROLE_NONE
from session_progress import arrive, status

NO3 = 0x41
HALL = (14, 40)
FLAG_POS_CAMERA_LOCKED = 0x08000000


def stage_entities(g):
    """{slot: (entityId, world x, world y, hp, camera-locked)} for slots 64-255."""
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    sx, sy = g.read("g_Tilemap", "<h", 0xA), g.read("g_Tilemap", "<h", 0xE)
    out = {}
    for slot in range(64, 256):
        e = raw[slot * 0xBC:(slot + 1) * 0xBC]
        eid = struct.unpack_from("<H", e, 0x26)[0]
        if eid:
            locked = bool(struct.unpack_from("<I", e, 0x34)[0] & FLAG_POS_CAMERA_LOCKED)
            x, y = struct.unpack_from("<h", e, 2)[0], struct.unpack_from("<h", e, 6)[0]
            out[slot] = (eid, x + sx if locked else x, y + sy if locked else y,
                         struct.unpack_from("<h", e, 0x3E)[0], locked)
    return out


def into_hall(run):
    """A walks into the hall and on a bit (authority); then B arrives next to A (guest)."""
    a, b = run.s.a, run.s.b
    bot = walker("left", attack_every=0)
    for i in range(1500):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if a.snapshot()["room"] == HALL and i > 200:
            break
    run.step(120)
    p = a.mailbox("self_presence")
    arrive(run, b, p.stage, p.room_id, p.ground_x + 24, p.ground_y)
    for _ in range(60):
        run.step(1)
        if b.mailbox("self_presence").role == ROLE_GUEST:
            break
    run.step(10)


def roles(run):
    return run.s.a.mailbox("self_presence").role, run.s.b.mailbox("self_presence").role


@session_scenario()
def shared_same_enemies(run):
    """M4 criteria 1 and 6: A is the authority and B the guest. B's world holds exactly A's
    stage entities, at the same room positions, with the same (normal) HP, and none of B's own."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.expect(roles(run) == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B the guest", roles=roles(run))
    run.step(30)
    ea, eb = stage_entities(a), stage_entities(b)
    enemies = {s: e for s, e in ea.items() if e[3] > 0}
    run.expect(enemies, "the hall has enemies", entities=len(ea))
    run.expect(set(eb) == set(ea), "B's world has exactly A's stage entities",
               only_a=sorted(set(ea) - set(eb))[:8], only_b=sorted(set(eb) - set(ea))[:8])
    off = [(s, ea[s], eb.get(s)) for s in ea if s in eb and ea[s][4] and
           (ea[s][0] != eb[s][0] or abs(ea[s][1] - eb[s][1]) > 1 or abs(ea[s][2] - eb[s][2]) > 1)]
    run.expect(not off, "at the same room positions (within 1 px; B's snapshot is a frame old)",
               off=off[:5], checked=sum(1 for s in ea if ea[s][4]))
    run.expect(all(eb[s][3] == ea[s][3] for s in enemies if s in eb), "with the same HP")


@session_scenario()
def guest_gets_hurt(run):
    """M4 criterion 3: B stands among the zombies; their attacks hurt B (in B's world, natively)."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    hp0 = status(b)["hp"]
    bot = walker("left", attack_every=0)
    for i in range(1500):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        if status(b)["hp"] < hp0:
            break
    run.expect(status(b)["hp"] < hp0, "an enemy hurt B", hp=status(b)["hp"], was=hp0, frames=i)
    run.expect(roles(run)[1] in (ROLE_GUEST, ROLE_NONE), "B was a guest (or wandered off on its own)")


WARG_SLOT = 96  # in the hall, idling just left of where A stands (into_hall)


@session_scenario()
def targeting_nearer_player(run):
    """M4 criterion 4, behaviour: the hall's Warg wakes when a player comes close. B walks
    toward it while A stays well out of its range: the Warg wakes for B and hits B."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    w = a.entity(WARG_SLOT)
    idle = a.read(w + 0x2C, "<H")
    sx = a.read("g_Tilemap", "<h", 0xA)
    warg_x = a.read(w + 2, "<h") + sx
    hp0 = status(b)["hp"]
    woke = None
    for i in range(400):
        run.step(1, p1=("", "left"))  # B keeps closing in; A never moves
        if a.read(w + 0x2C, "<H") != idle and woke is None:
            woke = (i, b.mailbox("self_presence").x, a.mailbox("self_presence").x)
        if woke and status(b)["hp"] < hp0:
            break
    run.expect(woke is not None, "the Warg woke up", idle_step=idle)
    dist_b, dist_a = abs(woke[1] - warg_x), abs(woke[2] - warg_x)
    run.expect(dist_b < dist_a, "for B, the nearer player", warg=warg_x, b=woke[1], a=woke[2])
    run.expect(status(b)["hp"] < hp0, "and went for B", hp=status(b)["hp"], was=hp0)


def _guest_hits(run):
    """The guest (B) attacks the hall's enemies while A, the authority, stands still: every hit B's
    world shows must land on A's real enemies. Returns (damage in B's world, damage landed in A's)."""
    from session_m15 import load_characters
    a, b = run.s.a, run.s.b
    load_characters(run)  # a character applies from the game's next load
    for g in (a, b):  # sturdy: the zombies mustn't kill anyone walking in (Maria starts weaker)
        g.write("g_Status", 999, "<i", 0x240)
        g.write("g_Status", 999, "<i", 0x23C)
    into_hall(run)
    run.expect(roles(run) == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B the guest", roles=roles(run),
               a=(a.snapshot()["room"], str(a.mailbox("self_presence"))[:400]), b=(b.snapshot()["room"], str(b.mailbox("self_presence"))[:400]))

    walk = walker("left", attack_every=12)
    bot = lambda i: walk(b.snapshot(), i)
    seen_b = seen_a = 0
    before_a, before_b = stage_entities(a), stage_entities(b)
    for i in range(900):
        run.step(1, p1=("", bot(i)))
        now_a, now_b = stage_entities(a), stage_entities(b)
        seen_a += sum(before_a[s][3] - e[3] for s, e in now_a.items() if s in before_a and before_a[s][0] == e[0] and e[3] < before_a[s][3])
        seen_b += sum(before_b[s][3] - e[3] for s, e in now_b.items() if s in before_b and before_b[s][0] == e[0] and e[3] < before_b[s][3])
        before_a, before_b = now_a, now_b
        if roles(run)[1] != ROLE_GUEST:
            break
    return seen_b, seen_a


def _guest_hits_test(name, characters):
    def test(run):
        seen_b, landed = _guest_hits(run)
        run.expect(seen_b >= 30, "the guest hurt enemies in its own world", damage=seen_b)
        # the guest's own count runs high (a snapshot puts a copy's HP back until the hit lands):
        # two Alucards land about 64% of it, two Marias 50% (2026-11-21)
        run.expect(landed >= seen_b * 2 // 5, "and that damage landed on the authority's enemies",
                   landed=landed, guest_saw=seen_b)
    test.__doc__ = f"The guest's hits land on the authority's enemies ({' and '.join(characters)}): a Reddit pair of Marias saw one player's hits do nothing."
    test.__name__ = name
    from link.mailbox import CHAR_ALUCARD, CHAR_MARIA, CHAR_SAT_MARIA
    ids = {"alucard": CHAR_ALUCARD, "maria": CHAR_MARIA, "saturn_maria": CHAR_SAT_MARIA}
    want = tuple(ids[c] for c in characters)
    session_scenario(characters=want, full=True)(test)


_guest_hits_test("guest_hits_land_maria_and_saturn_maria", ("maria", "saturn_maria"))


@session_scenario()
def shared_room_far_across_spawns_for_the_guest(run):
    """#355 (1.4.1): a stage spawns and keeps its entities only to 64 px past its screen, and a
    shared room's guest up to a screen across saw the authority's world end. A is the authority in
    the hall, B is 220 px left of it: A's stage windows reach B's screen."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    p = a.mailbox("self_presence")
    from session_progress import arrive
    arrive(run, b, p.stage, p.room_id, p.ground_x - 220, p.ground_y)
    for _ in range(120):
        run.step(1)
        if roles(run) == (ROLE_AUTHORITY, ROLE_GUEST):
            break
    run.step(60)
    across = b.read("g_Tilemap", "<h", 0xA) - a.read("g_Tilemap", "<h", 0xA)
    run.expect(roles(run) == (ROLE_AUTHORITY, ROLE_GUEST) and abs(across) > 96, "shared, B's camera far across from A's",
               roles=roles(run), across=across)
    from module import symbols
    extra = a.read(symbols()["g_CoopStageExtra"], "<i")
    run.expect(extra >= abs(across), "A's stage spawns, moves and keeps its entities out to B's screen",
               widened_by=extra, across=across)
    run.expect(b.read(symbols()["g_CoopStageExtra"], "<i") == 0, "B, the guest, doesn't widen its own",
               b=b.read(symbols()["g_CoopStageExtra"], "<i"))


RELIC_ROOM, TOP_SPOT, BOTTOM_SPOT = 120, (215, 135), (114, 391)  # the entrance's tall Cube of Zoe room


@session_scenario()
def shared_room_far_apart_vertically_not_shared(run):
    """#355: up and down, nothing widens the stage's windows, so a room is shared only while the
    cameras are within half a screen. A at the top of the tall relic room, B at its bottom: each runs its own."""
    from session_progress import arrive
    a, b = run.s.a, run.s.b
    arrive(run, a, NO3, RELIC_ROOM, *TOP_SPOT)
    arrive(run, b, NO3, RELIC_ROOM, *BOTTOM_SPOT)
    run.step(60)
    apart = b.read("g_Tilemap", "<h", 0xE) - a.read("g_Tilemap", "<h", 0xE)
    run.expect(apart > 128, "B's camera is well below A's", apart=apart)
    run.expect(roles(run) == (ROLE_NONE, ROLE_NONE), "the room isn't shared: each game runs its own", roles=roles(run))
    arrive(run, b, NO3, RELIC_ROOM, TOP_SPOT[0] - 24, TOP_SPOT[1])
    for _ in range(60):
        run.step(1)
    run.expect(ROLE_GUEST in roles(run), "together again at the top: shared", roles=roles(run))
