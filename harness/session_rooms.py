"""What the 0.14.0 playtest found in the castle's rooms: what a game's own player does in a shared
room, and doors. Each started as an F9 report."""

import struct

from session import session_scenario

from coop_env import TOOLS
from module import symbols
from session_progress import arrive

MARBLE = str(TOOLS["out"].parent / "fixtures" / "debug-starts" / "Marble Gallery.state")
NO0 = 0
ENTITY_SIZE = 0xBC
OVERLAY_ROOMS = 16  # g_api.o.rooms
TILEMAP_HEIGHT = 0x48
EAST_DOOR_ROOM, BEYOND_THE_DOOR = (45, 25), (60, 25)
LOCK_ROOM = (21, 34)
LOCK_X = 336
PLAYER_STEP = 0x2C
RICHTER_DEAD = 16
ANIM_FRAME = 0x56


def room_id(g, left, top):
    """The room's offset in the stage's room table (presence.room_id)."""
    rooms = g.read(g.addr("g_api") + OVERLAY_ROOMS)
    for at in range(0, 0x1000, 8):
        l, t, r, b = struct.unpack("4B", g.read_bytes(rooms + at, 4))
        if l == 0x40:
            break
        if (l, t) == (left, top):
            return at
    raise LookupError((left, top))


def walk(run, g, way, frames):
    pads = (way, "") if g is run.s.a else ("", way)
    run.step(frames, pads)


def _door_walk(run, g):
    arrive(run, g, NO0, room_id(g, *EAST_DOOR_ROOM), 3780, 136)
    rooms = []
    for t in range(600):
        walk(run, g, "right", 1)
        room = g.snapshot()["room"]
        if not rooms or rooms[-1] != room:
            rooms.append(room)
        if len(rooms) > 2:
            break
    run.expect(rooms[:2] == [EAST_DOOR_ROOM, BEYOND_THE_DOOR] and EAST_DOOR_ROOM not in rooms[1:],
               "through the door once, not back and forth", rooms=rooms)


@session_scenario(starts=(MARBLE, MARBLE), characters=(1, 0))
def door_gap_richter_walks_through(run):
    """Report 221050: the gap in the doorway's floor dropped Richter, and the wall bounced him
    through the door and back forever. A door's walk carries Alucard over it."""
    _door_walk(run, run.s.a)


@session_scenario(starts=(MARBLE, MARBLE), characters=(2, 0), full=True)
def door_gap_maria_walks_through(run):
    _door_walk(run, run.s.a)


@session_scenario(starts=(MARBLE, MARBLE), characters=(0, 1))
def door_gap_alucard_walks_through(run):
    _door_walk(run, run.s.a)


@session_scenario(starts=(MARBLE, MARBLE), characters=(0, 1))
def camera_limit_follows_the_guest(run):
    """Report 215551: a room's camera limits are set as a player walks past. The guest's copy of
    that entity never ran, so the guest kept the old limit and stood on it like a floor."""
    a, b = run.s.a, run.s.b
    rid = room_id(a, *LOCK_ROOM)
    arrive(run, a, NO0, rid, 372, 136)
    run.step(120)
    arrive(run, b, NO0, rid, 380, 136)
    run.step(60)
    roles = (a.mailbox("self_presence").role, b.mailbox("self_presence").role)
    run.expect(2 in roles, "the room is shared", roles=roles)
    guest = a if roles[0] == 2 else b
    before = guest.read("g_Tilemap", "<i", TILEMAP_HEIGHT)
    walk(run, guest, "left", 90)
    x = guest.snapshot()["world_x"]
    after = guest.read("g_Tilemap", "<i", TILEMAP_HEIGHT)
    run.expect(x < LOCK_X, "the guest walked past the limit", x=x)
    run.expect(after != before, "and its own camera's limit changed", before=before, after=after)
    walk(run, guest, "right", 90)
    run.expect(guest.read("g_Tilemap", "<i", TILEMAP_HEIGHT) != after, "and back", x=guest.snapshot()["world_x"])


@session_scenario(starts=(MARBLE, MARBLE), characters=(0, 1))
def partner_body_survives_its_hit_reaction(run):
    """Report 220241: the body runs its own damage code on the partner's real HP. It died of a hit
    the partner survived, and stayed dead and unseen."""
    a, b = run.s.a, run.s.b
    run.step(180)
    body = symbols()["g_CoopSpikeBody"]
    hits = symbols()["g_CoopBodyHits"]
    start = a.read(hits)
    hp = b.read("g_Status", "<i", 0x23C)
    for left in (hp // 2, hp // 4, 1):
        b.write(symbols_status(b), left, "<i")
        run.step(90)
        run.expect(a.read(body + PLAYER_STEP, "<H") != RICHTER_DEAD, "the body lives", hp=left)
    run.expect(a.read(hits) > start, "it took the hits", hits=a.read(hits) - start)


@session_scenario(starts=(MARBLE, MARBLE), characters=(0, 0))
def same_character_body_moves_as_the_partner(run):
    """Report 222713: two Alucards. A stands still while B runs: A's copy of B runs, and A doesn't."""
    a, b = run.s.a, run.s.b
    body = symbols()["g_CoopSpikeBody"]
    run.step(120)
    frames_body, frames_a = set(), set()
    for t in range(120):
        run.step(1, ("", "right"))
        frames_body.add(a.read(body + ANIM_FRAME, "<H") & 0x7FFF)
        frames_a.add(a.read(a.entity(0) + ANIM_FRAME, "<H") & 0x7FFF)
    run.expect(len(frames_a) == 1, "A stands", frames=sorted(frames_a))
    run.expect(len(frames_body) > 3, "A's copy of B runs", frames=sorted(frames_body))


def symbols_status(g):
    return g.addr("g_Status") + 0x23C
