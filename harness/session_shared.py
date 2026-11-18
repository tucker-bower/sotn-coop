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
