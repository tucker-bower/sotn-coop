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


E_RED_DOOR = 5


def red_doors(g):
    """(slot, x, y) of each red door in g's room, in world space."""
    sx, sy = g.read("g_Tilemap", "<h", 0xA), g.read("g_Tilemap", "<h", 0xE)
    out = []
    for slot in range(64, 256):
        e = g.entity(slot)
        if g.read(e + 0x26, "<H") == E_RED_DOOR and g.read(e + 0x2C, "<H"):
            out.append((slot, g.read(e + 2, "<h") + sx, g.read(e + 6, "<h") + sy))
    return out


@session_scenario()
def red_door_guest_copy_in_place(run):
    """#163: A (the authority) waits by the Cube of Zoe room's left door; B stands between the orb
    and the potion, almost a screen to the right, so B's game takes the door from A's snapshot
    instead of from its own layout. B's door is where A's is: the copy's setup used to move it a
    second time, 4 px right and 31 px down, out of reach, and it never opened for B (the report's
    state: Richter walks into the wall at x 38, the door at 16, and it opens within 16)."""
    a, b = run.s.a, run.s.b
    arrive(run, a, NO3, 120, 60, 120)
    run.step(60)
    arrive(run, b, NO3, 120, 360, 153 - STAND)
    run.step(120)
    run.expect(b.mailbox("self_presence").role == 2, "B is the guest", a=str(a.mailbox("self_presence")),
               b=str(b.mailbox("self_presence")))
    da, db = red_doors(a), red_doors(b)
    left = lambda ds: sorted((x, y) for _, x, y in ds if x < 64)
    run.expect(left(da) and left(db) == left(da), "B's left door is where A's is", a=da, b=db)


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


