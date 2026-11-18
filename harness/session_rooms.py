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
