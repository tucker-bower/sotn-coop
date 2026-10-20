"""M5 acceptance tests: bosses together (design/M5-bosses-cutscenes.md).

The boss on the test route is the Doppleganger in the Outer Wall: its room (NO1 cells 57-58,
row 23) is a boss teleport, so walking into it from the room to its right (room 96) loads the
boss overlay."""

import struct

from session import session_scenario  # first: puts `link` on the path

from link.mailbox import BOSS, BUSY, DEAD, IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST
from session_progress import arrive, status
from session_scenarios import heal

NO1 = 0x01
NEXT_TO_BOSS = (96, 40, 135)  # NO1 room 96 (59,23), near its left edge
DOPPLEGANGER10, DOPPLEGANGER10_HP = 253, 120  # enemy definition (assets/dra/us/enemydefs.yaml)
BOSS_STAGES = set(range(0x16, 0x1F)) | set(range(0x36, 0x3F))


def bosses(g):
    """{slot: (enemyId, hp, step)} of living boss-type entities (only the Doppleganger here)."""
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    out = {}
    for slot in range(64, 256):
        e = raw[slot * 0xBC:(slot + 1) * 0xBC]
        eid, enemy, hp = struct.unpack_from("<H", e, 0x26)[0], struct.unpack_from("<H", e, 0x3A)[0], \
            struct.unpack_from("<h", e, 0x3E)[0]
        if eid and enemy == DOPPLEGANGER10:
            out[slot] = (enemy, hp, struct.unpack_from("<H", e, 0x2C)[0])
    return out


def toward(g, owner, slot, i):
    """A pad for g: walk at the boss (owner's world, slot) and attack when close."""
    raw = owner.read_bytes(owner.entity(slot), 0xBC)
    boss_x = struct.unpack_from("<h", raw, 2)[0] + owner.read("g_Tilemap", "<h", 0xA)
    me = g.snapshot()["world_x"]
    side = "right" if boss_x > me else "left"
    if abs(boss_x - me) > 28:  # close in first: Alucard stops walking to punch
        return side
    return side + "+square" if i % 12 < 2 else side


def into_boss_room(run, g, limit=1800):
    """g arrives next to the Doppleganger's room and walks in. Returns frames until its presence
    shows a boss fight, or None."""
    arrive(run, g, NO1, *NEXT_TO_BOSS)
    for i in range(limit):
        run.step(1, p1=("left", "") if g is run.s.a else ("", "left"))
        if i % 30 == 0:
            heal(g)
        if g.mailbox("self_presence").flags & BOSS:
            return i
    return None


def wait_pulled(run, g, other, limit=1200):
    """Steps until g is in other's room, in play. Returns frames, or None."""
    for i in range(limit):
        run.step(1)
        if i % 30 == 0:
            heal(run.s.a), heal(run.s.b)
        p, q = g.mailbox("self_presence"), other.mailbox("self_presence")
        if p.room == q.room and p.flags & IN_PLAY and not p.flags & BUSY:
            return i
    return None


@session_scenario(starts=("no1", "entrance"))
def boss_pulls_partner_in(run):
    """M5 criteria 1-2: A walks into the Doppleganger's room; B (at the castle entrance) is
    pulled in within 5 s. The boss has twice its HP, in both worlds."""
    a, b = run.s.a, run.s.b
    t = into_boss_room(run, a)
    run.expect(t is not None, "A is in a boss fight", frames=t, stage=hex(a.snapshot()["stage"]))
    run.expect(a.snapshot()["stage"] in BOSS_STAGES, "in the boss overlay", stage=hex(a.snapshot()["stage"]))
    hp = [e[1] for e in bosses(a).values()]
    run.expect(hp and max(hp) == 2 * DOPPLEGANGER10_HP, "the Doppleganger has twice its HP", hp=hp)
    t = wait_pulled(run, b, a, 300)
    run.expect(t is not None, "B was pulled in within 5 s", frames=t, b=str(b.mailbox("self_presence").room))
    run.step(30)
    roles = (a.mailbox("self_presence").role, b.mailbox("self_presence").role)
    run.expect(roles == (ROLE_AUTHORITY, ROLE_GUEST), "A runs the fight, B is its guest", roles=roles)
    run.expect([e[1] for e in bosses(b).values()] == [e[1] for e in bosses(a).values()],
               "B sees the same boss, with the same HP", a=bosses(a), b=bosses(b))


@session_scenario(starts=("no1", "entrance"))
def boss_no_escape_by_map(run):
    """M5 part 1: in a boss fight, ✕ on the map doesn't teleport away."""
    from session_travel import map_teleport
    a, b = run.s.a, run.s.b
    t = into_boss_room(run, a)
    run.expect(t is not None, "A is in a boss fight", frames=t)
    room = a.mailbox("self_presence").room
    map_teleport(run, a)
    run.step(240)
    run.expect(a.mailbox("self_presence").room == room, "A is still in the boss room", room=str(room))


@session_scenario(starts=("no1", "entrance"))
def boss_both_hit_one_death(run):
    """M5 criterion 3: both players damage the boss; it dies once; the kill is recorded in both
    worlds (the boss room's teleport checks that record)."""
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    run.step(30)
    slot, (_, hp0, _) = next(iter(bosses(a).items()))
    hit_by = set()
    for i in range(3600):
        before = bosses(a).get(slot, (0, 0, 0))[1]
        who = (i // 300) % 2  # take turns: A for 5 s, then B
        g = a if who == 0 else b
        pad = toward(g, a, slot, i)
        run.step(1, p1=(pad, "") if who == 0 else ("", pad))
        if i % 20 == 0:
            heal(a), heal(b)
        after = bosses(a).get(slot, (0, 0, 0))[1]
        if after < before:
            hit_by.add("AB"[who])
        if slot not in bosses(a) or after <= 0:
            break
        if len(hit_by) == 2:
            a.write(a.entity(slot), 1, "<h", 0x3E)  # both have hit it: finish it (harness shortcut)
    run.expect(hit_by == {"A", "B"}, "both players hurt the boss", hit_by=sorted(hit_by))
    for i in range(1800):  # its death sequence
        run.step(1)
        if not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & BOSS:
            break
    run.expect(not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & BOSS,
               "the fight is over in both worlds", frames=i, a=bosses(a), b=bosses(b))
    run.step(120)
    rec = lambda g: [g.read("g_Settings", "<i", 0x30 + 4 * k) for k in range(32)]
    ra, rb = rec(a), rec(b)
    run.expect(any(ra) and ra == rb, "the kill is recorded in both worlds",
               a=[i for i, v in enumerate(ra) if v], b=[i for i, v in enumerate(rb) if v])


@session_scenario(starts=("no1", "entrance"))
def boss_dead_stays_down(run):
    """M5 criterion 5 (D24): A dies in the boss fight and stays down while B fights on; once B
    has beaten the boss, A respawns next to B with full HP."""
    from bots import walker
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    run.step(30)
    a.write("g_Status", 1, "<i", 0x23C)  # one hit from death (harness shortcut)
    bot = walker("right", attack_every=0)
    for i in range(3000):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if i % 20 == 0:
            heal(b)
        if a.mailbox("self_presence").flags & DEAD:
            break
    run.expect(a.mailbox("self_presence").flags & DEAD, "A died in the boss fight", frames=i)
    run.step(400)
    run.expect(a.mailbox("self_presence").flags & DEAD, "A stays down while the boss lives")
    run.expect(b.mailbox("self_presence").flags & BOSS and not b.mailbox("self_presence").flags & DEAD,
               "B fights on")
    for slot in bosses(b):  # B finishes the boss (harness shortcut: one hit left)
        b.write(b.entity(slot), 1, "<h", 0x3E)
    bot = walker("left", attack_every=6)
    for i in range(1800):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        if i % 20 == 0:
            heal(b)
        if not bosses(b):
            break
    run.expect(not bosses(b), "B beat the boss", frames=i)
    t = wait_pulled(run, a, b, 1800)
    st = status(a)
    run.expect(t is not None, "A respawned next to B", frames=t)
    run.expect(st["hp"] == st["hp_max"], "with full HP", hp=st["hp"])


NO0 = 0x00
LEFT_OF_MARIA = (80, 728, 135)  # NO0 room 80 (cells 29-31, row 26), near its right edge


@session_scenario(starts=("no0", "entrance"))
def cutscene_pulls_partner_in(run):
    """M5 criterion 6: A walks into the room where Maria is first met (a cutscene). B is pulled
    into A's room and goes through the scene too; afterwards the shared state matches."""
    from link.mailbox import CUTSCENE
    from session_scenarios import assert_converged
    a, b = run.s.a, run.s.b
    arrive(run, a, NO0, *LEFT_OF_MARIA)
    from bots import walker
    started = None
    bot = walker("right", attack_every=0)
    for i in range(1800):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if a.mailbox("self_presence").flags & CUTSCENE:
            started = i
            break
    run.expect(started is not None, "A's cutscene started", frames=i, stage=hex(a.snapshot()["stage"]))
    pulled = saw = None
    for i in range(1800):
        run.step(1)
        p, q = b.mailbox("self_presence"), a.mailbox("self_presence")
        if pulled is None and p.room == q.room and p.flags & IN_PLAY:
            pulled = i
        if pulled is not None and p.flags & CUTSCENE:
            saw = i
            break
    run.expect(pulled is not None and pulled < 300, "B was pulled into A's room within 5 s", frames=pulled)
    run.expect(saw is not None, "B's game ran the cutscene too", frames=saw)
    for _ in range(3600):  # let both scenes play out
        run.step(1)
        if not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & CUTSCENE:
            break
    run.step(120)
    assert_converged(run)


def aggro_hits(run, control=0):
    """The players stand at opposite ends of the boss room for up to a minute; returns how
    often the boss hurt each."""
    a, b = run.s.a, run.s.b
    a.mailbox("set_control", control)
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    room = a.mailbox("self_presence").room
    for _ in range(120):  # apart, but both stay in the boss room (its exits are open)
        pa = "left" if a.snapshot()["x"] > 40 else ""
        pb = "right" if b.snapshot()["x"] < 216 else ""
        run.step(1, p1=(pa, pb))
    run.expect(a.mailbox("self_presence").room == room == b.mailbox("self_presence").room,
               "both are in the boss room, apart", a=a.snapshot()["world_x"], b=b.snapshot()["world_x"])
    hurt = {"A": 0, "B": 0, "nearer_b": 0, "frames": 0}
    last = {"A": status(a)["hp"], "B": status(b)["hp"]}
    for i in range(3600):
        run.step(1)
        for slot in bosses(a):
            bx = struct.unpack_from("<h", a.read_bytes(a.entity(slot), 0xBC), 2)[0] + a.read("g_Tilemap", "<h", 0xA)
            hurt["nearer_b"] += abs(bx - b.snapshot()["world_x"]) < abs(bx - a.snapshot()["world_x"])
            hurt["frames"] += 1
        for name, g in (("A", a), ("B", b)):
            hp = status(g)["hp"]
            if hp < last[name]:
                hurt[name] += 1
            last[name] = hp
        if i % 10 == 0:
            heal(a), heal(b)
            last = {"A": status(a)["hp"], "B": status(b)["hp"]}
        if not bosses(a):
            break
    return hurt


@session_scenario(starts=("no1", "entrance"))
def boss_aggro_switches(run):
    """M5 criterion 4 (D47): the players stand at opposite ends of the boss room for a minute.
    The boss goes after both of them."""
    hurt = aggro_hits(run)
    switches = run.s.a.mailbox("self_presence").aggro_switches
    run.expect(switches >= 5, "the boss switched targets, again and again", switches=switches)
    run.expect(hurt["A"] > 0 and hurt["B"] > 0, "the boss hit both players", hits=hurt)


@session_scenario(starts=("no1", "entrance"))
def boss_aggro_control(run):
    """The control for boss_aggro_switches: with aggro switched off (CONTROL_NO_AGGRO), the boss
    never switches (so the counter boss_aggro_switches relies on means something). Where the
    boss goes isn't a good measure: the Doppleganger roams the whole (small) room either way."""
    from link.mailbox import CONTROL_NO_AGGRO
    switches0 = run.s.a.mailbox("self_presence").aggro_switches
    hurt = aggro_hits(run, CONTROL_NO_AGGRO)
    switches = run.s.a.mailbox("self_presence").aggro_switches - switches0
    run.expect(switches == 0, "the boss never switched to B", switches=switches, hits=hurt)


@session_scenario(starts=("no1", "entrance"))
def guest_blocked_by_closed_door(run):
    """M5 (and M4): the boss room's door closes in the authority's world; the guest can't walk
    out through it either (the room's tiles come with the snapshot)."""
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    room = a.mailbox("self_presence").room
    for i in range(300):
        run.step(1, p1=("", "right"))
        if i % 20 == 0:
            heal(a), heal(b)
    run.expect(b.mailbox("self_presence").room == room, "B is still in the boss room",
               b=str(b.mailbox("self_presence").room), x=b.snapshot()["x"])
