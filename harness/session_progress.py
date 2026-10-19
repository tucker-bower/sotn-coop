"""M2 acceptance tests: shared progression, live (design/M2-shared-progression.md).

Pickups are real: game A is put next to one with Arrive (CMD_ARRIVE, design/M3) and touches
it, so the game's own pickup code runs and our g_api wrappers see it. Locations are from the
stage layouts (assets/st/no3/entity_layouts.json) and NO3's prize table.
"""

from session import session_scenario  # first: puts `link` on the path

from link.mailbox import BUSY, CMD_ARRIVE, IN_PLAY

NO3 = 0x41
STATUS = "g_Status"
# PlayerStatus offsets (include/game.h)
RELICS, HAND_COUNT, BODY_COUNT = 0x00, 0x26, 0xCF
NUM_HAND, NUM_BODY = 169, 90
SPELLS_LEARNT, HP, HP_MAX, HEARTS_MAX, LEVEL, EXP, GOLD, SUBWEAPON, EQUIPMENT = (
    0x238, 0x23C, 0x240, 0x248, 0x284, 0x288, 0x28C, 0x298, 0x29C)

# Castle entrance pickups: (roomId, x, y). roomId is the RoomHeader offset in NO3's room table.
CUBE_OF_ZOE = (120, 272, 114)   # relic orb, relic 10
SHIELD_POTION = (120, 440, 153)  # same room as the Cube of Zoe: consumable
HOLY_MAIL = (24, 80, 89)        # body armour
LIFE_APPLE = (64, 128, 153)     # consumable
LIFE_VESSEL = (136, 160, 169)   # Life Max Up
HEART_VESSEL = (112, 96, 169)   # Heart Max Up
RELIC_CUBE_OF_ZOE = 10


def status(g):
    raw = g.read_bytes(STATUS, 0x334)
    i32 = lambda o: int.from_bytes(raw[o:o + 4], "little", signed=True)
    return {
        "relics": raw[RELICS:RELICS + 30], "hand": raw[HAND_COUNT:HAND_COUNT + NUM_HAND],
        "body": raw[BODY_COUNT:BODY_COUNT + NUM_BODY], "spells": i32(SPELLS_LEARNT), "hp": i32(HP),
        "hp_max": i32(HP_MAX), "hearts_max": i32(HEARTS_MAX), "level": i32(LEVEL), "exp": i32(EXP),
        "gold": i32(GOLD), "subweapon": i32(SUBWEAPON), "equipment": raw[EQUIPMENT:EQUIPMENT + 28],
    }


def counts(st):
    return sum(st["hand"]) + sum(st["body"])


def arrive(run, g, stage, room_id, x, y, limit=900):
    """Sends game g to (stage, room_id, x, y) and steps until it's in play there."""
    g.mailbox("command", CMD_ARRIVE, stage, room_id, x, y)
    for i in range(limit):
        run.step(1)
        p = g.mailbox("self_presence")
        if p.stage == stage and p.room_id == room_id and p.flags & IN_PLAY and not p.flags & BUSY:
            return i
    run.expect(False, f"game {g.name} arrives in room {room_id} of stage {stage:#x}", presence=str(p))


STAND = 18  # a standing player's y is this far above an item resting on the same floor


def take(run, g, spot, frames=240):
    """Arrive on a pickup in NO3, then let the game's pickup code run (and any message box).
    Relic orbs float, so the player goes where the orb is; items rest on a floor, so the player
    stands on that floor."""
    room_id, x, y = spot
    arrive(run, g, NO3, room_id, x, y if spot == CUBE_OF_ZOE else y - STAND)
    run.step(frames)


@session_scenario()
def relic_shared(run):
    """M2 criterion 1: A picks up a relic; B has it (found + active) within 3 frames."""
    a, b = run.s.a, run.s.b
    run.expect(not status(b)["relics"][RELIC_CUBE_OF_ZOE], "B doesn't have the Cube of Zoe yet")
    arrive(run, a, NO3, *CUBE_OF_ZOE)
    for i in range(600):
        run.step(1)
        if status(a)["relics"][RELIC_CUBE_OF_ZOE]:
            break
    run.expect(status(a)["relics"][RELIC_CUBE_OF_ZOE] & 1, "A picked up the Cube of Zoe", frame=i)
    lag = None
    for j in range(10):
        if status(b)["relics"][RELIC_CUBE_OF_ZOE] & 1:
            lag = j
            break
        run.step(1)
    run.expect(lag is not None and lag <= 3, "B has it within 3 frames", frames=lag,
               value=status(b)["relics"][RELIC_CUBE_OF_ZOE])
    run.expect(status(b)["relics"][RELIC_CUBE_OF_ZOE] == status(a)["relics"][RELIC_CUBE_OF_ZOE],
               "found and active, as for A", a=status(a)["relics"][RELIC_CUBE_OF_ZOE])


@session_scenario()
def items_and_maxups_shared(run):
    """M2 criteria 2, 3 and 6: equipment and consumables reach B (D37), Life and Heart Max Ups
    raise B's maximums by the same amount, the pickups are gone from B's world (flags), and
    what's separate stays separate."""
    a, b = run.s.a, run.s.b
    b0, a0 = status(b), status(a)
    for spot in (HOLY_MAIL, LIFE_APPLE, LIFE_VESSEL, HEART_VESSEL):
        take(run, a, spot)
    run.step(10)
    a1, b1 = status(a), status(b)
    run.expect(counts(a1) - counts(a0) >= 2, "A picked up the Holy Mail and the Life Apple",
               gained=counts(a1) - counts(a0))
    gained_a = [(i, a1["body"][i] - a0["body"][i]) for i in range(NUM_BODY) if a1["body"][i] != a0["body"][i]]
    gained_a += [(i + 1000, a1["hand"][i] - a0["hand"][i]) for i in range(NUM_HAND) if a1["hand"][i] != a0["hand"][i]]
    gained_b = [(i, b1["body"][i] - b0["body"][i]) for i in range(NUM_BODY) if b1["body"][i] != b0["body"][i]]
    gained_b += [(i + 1000, b1["hand"][i] - b0["hand"][i]) for i in range(NUM_HAND) if b1["hand"][i] != b0["hand"][i]]
    run.expect(gained_a and gained_b == gained_a, "B gained exactly the items A found", a=gained_a, b=gained_b)
    run.expect(a1["hp_max"] - a0["hp_max"] == 5 and b1["hp_max"] - b0["hp_max"] == 5,
               "Life Max Up: +5 max HP in both", a=a1["hp_max"] - a0["hp_max"], b=b1["hp_max"] - b0["hp_max"])
    run.expect(a1["hearts_max"] - a0["hearts_max"] == 5 and b1["hearts_max"] - b0["hearts_max"] == 5,
               "Heart Max Up: +5 max hearts in both",
               a=a1["hearts_max"] - a0["hearts_max"], b=b1["hearts_max"] - b0["hearts_max"])
    fa, fb = a.read_bytes("g_CastleFlags", 0x300), b.read_bytes("g_CastleFlags", 0x300)
    run.expect(fa[0x100:0x190] == fb[0x100:0x190] and fa[0x100:0x190] != bytes(0x90),
               "the pickups are marked taken in B's world too")
    run.expect(all(b1[k] == b0[k] for k in ("level", "exp", "spells", "subweapon", "equipment")),
               "B's level, XP, spells, subweapon and equipped items didn't change",
               changed=[k for k in ("level", "exp", "spells", "subweapon", "equipment") if b1[k] != b0[k]])


@session_scenario()
def gold_pooled(run):
    """D38: gold is one purse. A's gold changes (a stand-in for a money bag or a purchase: a
    harness poke) reach B as the same change, and B's spending reaches A."""
    a, b = run.s.a, run.s.b
    run.step(5)
    g0 = status(a)["gold"]
    run.expect(g0 == status(b)["gold"], "same purse to start", a=g0, b=status(b)["gold"])
    a.write(STATUS, g0 + 400, "<i", GOLD)
    run.step(5)
    run.expect(status(b)["gold"] == g0 + 400, "A +400: B sees +400", b=status(b)["gold"])
    b.write(STATUS, status(b)["gold"] - 150, "<i", GOLD)
    run.step(5)
    run.expect(status(a)["gold"] == status(b)["gold"] == g0 + 250, "B -150: both at +250",
               a=status(a)["gold"], b=status(b)["gold"])


def entities(g, ids):
    out = []
    for slot in range(64, 256):
        e = g.entity(slot)
        eid, step = g.read(e + 0x26, "<H"), g.read(e + 0x2C, "<H")
        if eid in ids and step:
            out.append((slot, eid, g.read(e + 0x30, "<H"), g.read(e + 0xB4, "<H")))
    return out


@session_scenario()
def live_despawn(run):
    """M2 criterion 5 (pickups): B stands in the Cube of Zoe's room, with the orb and the Shield
    Potion on its screen. A takes both in its own world. In B's world they vanish within 5 frames,
    without B leaving the room, and B gets each exactly once."""
    a, b = run.s.a, run.s.b
    arrive(run, b, NO3, 120, 360, 153 - STAND)  # between the orb and the potion
    run.step(60)
    before = entities(b, (0x0B, 0x0C))
    run.expect(any(e[1] == 0x0B for e in before) and any(e[1] == 0x0C for e in before),
               "B's world shows the relic orb and the potion", entities=before)
    room_b = b.mailbox("self_presence").room
    b0 = status(b)
    take(run, a, CUBE_OF_ZOE, frames=0)
    gone, waited = None, 0
    for waited in range(600):
        run.step(1)
        if status(a)["relics"][RELIC_CUBE_OF_ZOE] and not any(e[1] == 0x0B for e in entities(b, (0x0B,))):
            gone = waited
            break
    run.expect(gone is not None, "the orb vanished from B's world", after=entities(b, (0x0B, 0x0C)))
    take(run, a, SHIELD_POTION, frames=0)
    for waited in range(600):
        run.step(1)
        if not any(e[1] == 0x0C for e in entities(b, (0x0C,))):
            break
    run.expect(not any(e[1] == 0x0C for e in entities(b, (0x0C,))), "the potion vanished from B's world")
    run.step(30)
    run.expect(b.mailbox("self_presence").room == room_b, "B never left the room")
    b1 = status(b)
    run.expect(b1["relics"][RELIC_CUBE_OF_ZOE] & 1 and counts(b1) - counts(b0) == 1,
               "B got the relic once and the potion once", items=counts(b1) - counts(b0))


@session_scenario()
def exactly_once_partition(run):
    """M2 criterion 7: the network drops everything for 10 s while A picks up two things; once
    it's back, B gets each exactly once and the shared state converges."""
    from session_scenarios import assert_converged
    a, b = run.s.a, run.s.b
    b0 = status(b)
    a.partition(True), b.partition(True)
    take(run, a, HOLY_MAIL)
    take(run, a, LIFE_VESSEL)
    run.expect(status(b)["hp_max"] == b0["hp_max"], "nothing reached B during the partition")
    run.step(600 - 480)
    a.partition(False), b.partition(False)
    run.step(60)
    b1 = status(b)
    run.expect(counts(b1) - counts(b0) == 1 and b1["hp_max"] - b0["hp_max"] == 5,
               "after the partition, B got the Holy Mail and +5 max HP exactly once",
               items=counts(b1) - counts(b0), hp_max=b1["hp_max"] - b0["hp_max"])
    run.step(30)
    run.expect(status(b)["hp_max"] - b0["hp_max"] == 5, "and nothing twice, later")
    assert_converged(run)


@session_scenario()
def map_shared(run):
    """M2 criterion 4: A explores rooms by arriving in them; B's map equals the union, and both
    room counts match the explored cells."""
    a, b = run.s.a, run.s.b
    for spot in (HOLY_MAIL, LIFE_APPLE, HEART_VESSEL, LIFE_VESSEL):
        arrive(run, a, NO3, *spot)
        run.step(30)
    run.step(10)
    ma, mb = a.read_bytes("g_CastleMap", 0x800), b.read_bytes("g_CastleMap", 0x800)
    run.expect(ma == mb, "B's map equals A's (B explored nothing new itself)")
    explored = sum(bin(x & 0x55).count("1") for x in mb)
    ra, rb = a.read("g_RoomCount"), b.read("g_RoomCount")
    run.expect(ra == rb == explored, "both room counts equal the explored cells", a=ra, b=rb, cells=explored)


NZ0 = 0x0C
NZ0_SECRET_WALL_OPEN = 0x81
E_LEFT_SECRET_WALL = 0x17  # NZ0 entity id (src/st/nz0/nz0.h)
SECRET_WALL_ROOM = 112     # NZ0 room (12,32)-(12,34); the wall is at (16, 640)


@session_scenario()
def live_object_refresh(run):
    """M2 criterion 5 (objects): B stands by the Alchemy Lab's left secret wall. A opens it in
    A's world (a harness poke of NZ0_SECRET_WALL_OPEN stands in for breaking it). In B's world
    the wall's own init runs again: it opens (room tiles change, the entity goes) within 5 frames,
    and B never leaves the room. Also checks the generated table's report exists."""
    from coop_env import COOP
    a, b = run.s.a, run.s.b
    arrive(run, b, NZ0, SECRET_WALL_ROOM, 72, 640)
    run.step(90)
    wall = [s for s in range(64, 256) if b.read(b.entity(s) + 0x26, "<H") == E_LEFT_SECRET_WALL]
    run.expect(wall, "B's world has the closed secret wall", room=b.mailbox("self_presence").room)
    fg = b.read("g_Tilemap", "<I", 0)  # g_Tilemap.fg: the room's foreground tile indices
    fg0 = b.read_bytes(fg, 0x800)
    room_b = b.mailbox("self_presence").room
    a.write("g_CastleFlags", 1, "<B", NZ0_SECRET_WALL_OPEN)
    gone = None
    for i in range(30):
        run.step(1)
        if b.read(b.entity(wall[0]) + 0x26, "<H") != E_LEFT_SECRET_WALL:
            gone = i
            break
    run.expect(gone is not None and gone <= 5, "the wall opened in B's world within 5 frames", frames=gone)
    run.expect(b.read("g_CastleFlags", "<B", NZ0_SECRET_WALL_OPEN) == 1, "B has the flag")
    fg1 = b.read_bytes(fg, 0x800)
    run.expect(fg0 != fg1, "B's room tiles changed (the wall's tiles were rewritten as open)")
    run.expect(b.mailbox("self_presence").room == room_b, "B never left the room")
    report = (COOP / "docs/flag-gated-entities.md").read_text()
    run.expect("EntityLeftSecretRoomWall" in report and report.count("\n- ") > 100,
               "the generated report lists the flag-gated entities", entries=report.count("\n- "))
