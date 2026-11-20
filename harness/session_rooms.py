"""What the 0.14.0 playtest found in the castle's rooms: what a game's own player does in a shared
room, and doors. Each started as an F9 report."""

import struct

from session import session_scenario

from link.mailbox import CUTSCENE, FLIP_SKIP_VOTE, PAUSED

from coop_env import TOOLS
from link.mailbox import scene_speed
from session_m8 import reload_game

NO0 = 0
ENTITY_SIZE = 0xBC
OVERLAY_ROOMS = 16  # g_api.o.rooms
EAST_DOOR_ROOM, BEYOND_THE_DOOR = (45, 25), (60, 25)


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


SCENE = str(TOOLS["out"].parent / "fixtures" / "debug-starts" / "Scene - Maria in the Alchemy Lab.state")


@session_scenario(starts=(SCENE, SCENE))
def scene_skips_once_both_players_ask(run):
    """Issue 107: Start skips a scene, but only when both players have pressed it."""
    a, b = run.s.a, run.s.b
    for t in range(1200):
        run.step(1, ("left", "left"))
        if a.mailbox("self_presence").flags & CUTSCENE and b.mailbox("self_presence").flags & CUTSCENE:
            break
    run.expect(a.mailbox("self_presence").flags & CUTSCENE, "the scene is on", t=t)
    run.step(120)
    run.step(2, ("start", ""))
    run.step(120)
    run.expect(a.mailbox("self_presence").flip_x & FLIP_SKIP_VOTE, "A asked to skip")
    run.expect(not b.mailbox("self_presence").flip_x & FLIP_SKIP_VOTE, "B hasn't")
    run.expect(scene_speed([a.mailbox("self_presence"), b.mailbox("self_presence")], False) == 1,
               "one vote doesn't speed it up")
    run.step(2, ("", "start"))
    run.step(30)
    votes = [g.mailbox("self_presence") for g in (a, b)]
    run.expect(scene_speed(votes, False) > 1, "two votes do", votes=[v.flip_x for v in votes])
    run.step(2)


ICON_AREA = (0x280, 0x180, 32, 32), (0, 0xFD, 256, 2)  # VRAM: the pickup icons' tiles, their palettes


def icons(g):
    return [g.vram_rect(*area) for area in ICON_AREA]


EQUIPMENT = 0x80097C00            # g_Status.equipment: the hands
WEAPON_PRG = (0x8017A000, 0x8017D000)
LAB = str(TOOLS["out"].parent / "fixtures" / "debug-starts" / "Alchemy Laboratory.state")


BODY_COUNT = 0x80097A33  # g_Status.equipBodyCount: armour in the bag
BODY_ORDER = 0x80097B36  # g_Status.equipBodyOrder: the order the menu lists it in
PLATINUM_MAIL, HEALING_MAIL_ID, ARMOR_SLOT = 0x08, 0x11, 0x80097C0C


@session_scenario(starts=(LAB, LAB), characters=(1, 0))
def unpause_after_changing_armour_richter_and_alucard(run):
    """Issue 194 (0.16.3): paused as Richter after a load, swapped Healing Mail for Platinum Mail in
    the equipment menu, and the game hung on unpausing. Through the real menu: Equip, Body, the
    Platinum Mail (put next to Unequip in the list), then back out and unpause."""
    import os
    a = run.s.a
    out = os.environ.get("COOP_SHOTS")
    run.step(30)
    run.expect(reload_game(run, a), "Continue's load brings this game's player in")
    a.write(ARMOR_SLOT, HEALING_MAIL_ID, "<I")
    a.write(BODY_COUNT + PLATINUM_MAIL, 1, "<B")
    order = list(a.read_bytes(BODY_ORDER, 90))  # the list's order: the Platinum Mail second, beside Unequip
    at = order.index(PLATINUM_MAIL)
    order[1], order[at] = order[at], order[1]
    a.write_bytes(BODY_ORDER, bytes(order))
    run.step(60)
    for k, (button, frames, gap) in enumerate((("start", 7, 60), ("cross", 6, 40), ("down", 4, 12), ("down", 4, 12),
                                               ("down", 4, 12), ("cross", 6, 30), ("right", 4, 12), ("cross", 6, 30),
                                               ("triangle", 6, 30), ("triangle", 6, 30), ("triangle", 6, 60))):
        run.step(frames, (button, ""))
        run.step(gap)
        if out:
            a.screenshot().save(f"{out}/{k:02d}-{button}.png")
    run.expect(a.read(ARMOR_SLOT, "<I") == PLATINUM_MAIL, "the menu put the Platinum Mail on",
               armour=hex(a.read(ARMOR_SLOT, "<I")))
    beat, frame = a.mailbox("heartbeat"), a.mailbox("self_presence").frame
    run.step(300)
    p = a.mailbox("self_presence")
    run.expect(a.mailbox("heartbeat") != beat, "the main loop runs after unpausing", beat=(beat, a.mailbox("heartbeat")))
    run.expect(p.frame != frame and not p.flags & PAUSED, "the game's timer runs after unpausing",
               frame=(frame, p.frame), flags=p.flags)


ELEVATOR_ID = 0x47  # NZ0's EntityElevator (src/st/nz0/e_elevator.c)
NZ0 = 0x0C


def _elevator(g):
    """(slot, its y in the room) of the Alchemy Lab's elevator in g, or None."""
    sy = g.read("g_Tilemap", "<h", 0xE)
    for slot in range(64, 256):
        if g.read("g_Entities", "<H", slot * ENTITY_SIZE + 0x26) == ELEVATOR_ID:
            return slot, g.read("g_Entities", "<h", slot * ENTITY_SIZE + 6) + sy
    return None


def _ride(run, rider, way, frames=600):
    """rider presses `way` in the elevator; [(elevator y, rider's y in the room)] each 30 frames."""
    pads = lambda pad: (pad, "") if rider is run.s.a else ("", pad)
    out = []
    run.step(10, pads(way))
    for t in range(frames):
        run.step(1)
        if t % 30 == 0:
            e = _elevator(rider)
            out.append((e and e[1], rider.snapshot()["world_y"]))
    return out


@session_scenario(starts=("nz0", "nz0"), characters=(1, 0))
def shared_room_elevator_richter_and_alucard(run):
    """#297 (1.1.1 playtest: "Richter and Maria have trouble on the elevator"): the Alchemy Lab's
    elevator reads Up and Down from the player in it. With both in it, it read only its own game's
    player (the room's authority): the other could never send it. Here Richter (A) rides it up
    alone, then Alucard (B, the guest) joins him and sends it down: it goes, with both aboard."""
    from session_progress import arrive
    a, b = run.s.a, run.s.b
    run.step(60)
    room = room_id(a, 17, 28)
    arrive(run, a, NZ0, room, 144, 560)
    run.step(60)
    ride = _ride(run, a, "up")
    run.expect(ride[-1][0] < ride[0][0] - 300 and abs((ride[-1][1] - ride[-1][0]) - (ride[0][1] - ride[0][0])) <= 2,
               "Richter sends it up and rides it", ride=ride[::5])
    arrive(run, b, NZ0, room, 144, 100)
    run.step(120)
    roles = [g.mailbox("self_presence").role for g in (a, b)]
    run.expect(roles == [1, 2] and b.mailbox("self_presence").stand_slot, "both in it: Alucard the guest, standing on it",
               roles=roles, stand=b.mailbox("self_presence").stand_slot)
    ride = _ride(run, b, "down")
    top = ride[0][0]
    run.expect(ride[-1][0] > top + 300, "the guest sends it down", ride=ride[::5])
    for g in (a, b):  # each stands on its own game's elevator, where it stopped
        y, cage = g.snapshot()["world_y"], _elevator(g)[1]
        run.expect(abs(y - (cage + 39)) <= 3, f"{g.name} rode it down", y=y, elevator=cage)


@session_scenario(starts=("nz0", "nz0"), characters=(0, 1))
def shared_room_lift_on_lag_alucard_and_richter(run):
    """#292 (1.1.1 playtest: "Desync affects gameplay, Richter can Moon Jump"): on the playtest's
    network, a guest standing on a rising lift (the Alchemy Lab's elevator, sent up by the
    authority) fell through it when a late snapshot moved it several frames' worth at once.
    Richter (the guest) rides it all the way up, standing on it every frame."""
    from session_progress import arrive
    a, b = run.s.a, run.s.b
    run.step(60)
    room = room_id(a, 17, 28)
    arrive(run, a, NZ0, room, 144, 560)
    arrive(run, b, NZ0, room, 144, 560)
    run.s.set_net("playtest")
    run.step(120)
    roles = [g.mailbox("self_presence").role for g in (a, b)]
    run.expect(roles == [1, 2], "Alucard runs the room, Richter is the guest", roles=roles)
    start = _elevator(b)[1]
    run.step(10, ("up", ""))
    gaps = []
    for t in range(700):
        run.step(1)
        gaps.append(b.snapshot()["world_y"] - _elevator(b)[1])
    run.expect(_elevator(b)[1] < start - 400, "the elevator went up", start=start, now=_elevator(b)[1])
    run.expect(max(gaps) - min(gaps) <= 3, "Richter stood on it all the way", gaps=sorted(set(gaps))[:8])


@session_scenario(starts=("entrance", "entrance"), characters=(1, 0))
def partner_body_faces_the_partners_way_richter_and_alucard(run):
    """#274: a body made facing the other way kept it until the partner pressed left or right, so a
    sub-weapon thrown with no direction flew backwards on the other screen. Richter (A) turns left
    and stands; in Alucard's game (B) his body is turned the wrong way: it faces left again within
    a few frames, as A does."""
    from session_three import body
    a, b = run.s.a, run.s.b
    run.step(120)
    run.step(20, ("left", ""))
    run.step(60)
    run.expect(a.read(a.entity(0), "<H", 0x14) == 1, "Richter faces left")
    b.write(body(b, 0), 0, "<H", 0x14)  # B's copy of him, made facing right
    run.step(10)
    run.expect(b.read(body(b, 0), "<H", 0x14) == 1, "his body in Alucard's game faces left again",
               facing=b.read(body(b, 0), "<H", 0x14))
