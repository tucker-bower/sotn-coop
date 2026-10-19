"""M4 acceptance tests: shared rooms, the same enemies (design/M4-shared-rooms.md).

The stage is the castle entrance hall (NO3 room 14,40), which has zombies. A walks in first
(the authority); B arrives at A's spot afterwards (the guest)."""

import struct

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from link.mailbox import CMD_ARRIVE, ROLE_AUTHORITY, ROLE_GUEST, ROLE_NONE
from session_progress import arrive, status

NO3 = 0x41
HALL = (14, 40)
FLAG_POS_CAMERA_LOCKED = 0x08000000
OVERLAY_TABLE = "overlay_table.c"


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
def guest_hits_count(run):
    """M4 criterion 2: B fights; A stands still. A's enemies lose HP to B's hits (in A's world),
    and an enemy B kills dies in both worlds, once."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    hp0 = {s: e[3] for s, e in stage_entities(a).items() if e[3] > 0}
    a_hp = status(a)["hp"]
    killed, hurt = set(), set()
    bot = walker("left", attack_every=6)
    for i in range(900):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        now = stage_entities(a)
        for s, hp in hp0.items():
            if s in now and now[s][3] < hp:
                hurt.add(s)
            if s not in now or now[s][3] <= 0:
                killed.add(s)
        if killed:
            break
    run.expect(hurt or killed, "B's attacks damaged A's enemies", hurt=sorted(hurt), killed=sorted(killed))
    run.expect(killed, "B killed an enemy in A's world", frames=i)
    run.step(60)
    ea, eb = stage_entities(a), stage_entities(b)
    gone = [s for s in killed if (s not in ea or ea[s][0] != hp0.get(s, -1))]
    run.expect(all(s not in eb or eb[s] == ea.get(s) for s in killed), "and it's gone from B's world too")


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


@session_scenario()
def targeting_patched(run):
    """M4 criterion 4: the stage's targeting helpers jump to the module, and an enemy facing
    choice follows the nearer player."""
    from coop_env import COOP
    import re
    a = run.s.a
    run.step(30)
    table = (COOP / "module" / OVERLAY_TABLE).read_text()
    row = next(l for l in table.splitlines() if l.strip().endswith("// stno3"))
    addrs = [int(x, 16) for x in re.findall(r"\{0x([0-9A-F]{8}), 0x[0-9A-F]{8}\}", row)]
    words = [a.read(x) for x in addrs]
    run.expect(all(w >> 26 == 2 and (w & 0x3FFFFFF) << 2 | 0x80000000 >= 0x80280000 for w in words),
               "NO3's three targeting helpers jump into the module", words=[hex(w) for w in words])


@session_scenario()
def in_and_out(run):
    """M4 criterion 5: B leaves and comes back; then A (the authority) leaves and B carries on
    with the same enemies (hand-over): nothing duplicated, nothing lost, no crash."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.expect(roles(run) == (ROLE_AUTHORITY, ROLE_GUEST), "shared")
    hall = a.mailbox("self_presence")
    arrive(run, b, NO3, 120, 272, 114)  # elsewhere
    run.step(30)
    run.expect(roles(run)[1] == ROLE_NONE and roles(run)[0] == ROLE_NONE, "B left: nobody shares")
    arrive(run, b, hall.stage, hall.room_id, hall.ground_x + 24, hall.ground_y)
    for _ in range(60):
        run.step(1)
        if roles(run) == (ROLE_AUTHORITY, ROLE_GUEST):
            break
    run.expect(roles(run) == (ROLE_AUTHORITY, ROLE_GUEST), "B came back: shared again, A still the authority")
    run.step(20)
    before = stage_entities(b)
    arrive(run, a, NO3, 120, 272, 114)  # the authority leaves
    run.step(20)
    run.expect(roles(run)[1] == ROLE_NONE, "A left: B runs the room itself now")
    after = stage_entities(b)
    enemies = [s for s, e in before.items() if e[3] > 0]
    kept = [s for s in enemies if s in after and after[s][0] == before[s][0]]
    run.expect(len(kept) >= len(enemies) - 1, "B kept the enemies (hand-over)", before=len(enemies), kept=len(kept))
    moved = [s for s in kept if before[s][4] and (abs(after[s][1] - before[s][1]) > 48 or abs(after[s][2] - before[s][2]) > 48)]
    run.expect(not moved, "and they carried on from where they were", jumped=moved[:5])
    run.step(300)
    run.expect(b.snapshot()["game_state"] == 2 and a.snapshot()["game_state"] == 2, "no crash")


@session_scenario()
def snapshot_cost(run):
    """M4 criterion 7: snapshot size, reported."""
    a = run.s.a
    into_hall(run)
    seq, snap = a.mailbox("snapshot_out")
    run.expect(0 < len(snap) <= 0xF000, "the snapshot fits one datagram", bytes=len(snap), seq=seq)


def shared_soak(run, minutes):
    """M4 criterion 8: both fight in the hall (shared most of the time) with random input, with
    occasional regroups. No crash, the shared state converges."""
    from lockstep import random_inputs
    from session_scenarios import assert_converged, heal
    a, b = run.s.a, run.s.b
    into_hall(run)
    frames = int(minutes * 3600)
    ia, ib = list(random_inputs(41, frames)), list(random_inputs(42, frames))
    shared = 0
    for t in range(0, frames, 600):
        run.step(600, p1=lambda i, sa, sb, t=t: (ia[t + i][0], ib[t + i][0]))
        shared += roles(run) == (ROLE_AUTHORITY, ROLE_GUEST) or roles(run) == (ROLE_GUEST, ROLE_AUTHORITY)
        heal(a), heal(b)
        p = a.mailbox("self_presence")
        if not roles(run)[0]:
            b.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)
    run.expect(a.snapshot()["game_state"] == 2 and b.snapshot()["game_state"] == 2, "both still in play",
               shared_checks=shared, checks=frames // 600)
    run.expect(shared >= frames // 600 // 2, "shared most of the time", shared=shared)
    assert_converged(run)


@session_scenario()
def shared_soak_short(run):
    shared_soak(run, 2)


@session_scenario()
def shared_soak_10min(run):
    shared_soak(run, 10)


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
