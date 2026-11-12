"""What the 0.14.0 playtest found in the castle's rooms: what a game's own player does in a shared
room, and doors. Each started as an F9 report."""

import struct

from session import session_scenario

from link.mailbox import CUTSCENE, FLIP_SKIP_VOTE, PAUSED

from coop_env import TOOLS
from link.mailbox import scene_speed
from module import symbols
from session_progress import arrive
from session_m8 import reload_game

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
BOTTOM_TEXT_TIMER = 0x80097410  # g_unkGraphicsStruct.BottomCornerTextTimer


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


SPELL_DARK_METAMORPHOSIS_STEP = 32  # Player_SpellDarkMetamorphosis (include/player_steps.h)


@session_scenario(starts=(MARBLE, MARBLE), characters=(0, 0))
def partner_casts_a_spell_this_game_never_learnt(run):
    """Issue 122: A knows Dark Metamorphosis and B doesn't. A casts it, and B's copy of A casts it
    too: the body checks the partner's spells, not this game's."""
    from link.mailbox import OPT_PARTNER_SIM, OPT_SHORTCUTS, SPELLS, spell_options
    from scenarios_m8 import MP, MP_MAX, SPELLS_LEARNT
    a, b = run.s.a, run.s.b
    body = symbols()["g_CoopSpikeBody"]
    choice = spell_options([None, None, None, SPELLS.index("Dark Metamorphosis")])
    a.host("set_player", options=OPT_PARTNER_SIM | OPT_SHORTCUTS | choice)
    b.host("set_player", options=OPT_PARTNER_SIM)
    a.write(SPELLS_LEARNT, 0xFF)
    b.write(SPELLS_LEARNT, 0)
    for g in (a, b):
        g.write(MP, 99, "<i")
        g.write(MP_MAX, 99, "<i")
    run.step(120)
    run.expect(not b.read(SPELLS_LEARNT) & 0xFF, "B hasn't learnt it")
    cast_a, cast_body = False, False
    for t in range(240):
        run.step(1, ("rs_left" if t % 120 < 2 else "", ""))
        cast_a |= a.read(a.entity(0) + PLAYER_STEP, "<H") == SPELL_DARK_METAMORPHOSIS_STEP
        cast_body |= b.read(body + PLAYER_STEP, "<H") == SPELL_DARK_METAMORPHOSIS_STEP
    run.expect(cast_a, "A casts it")
    run.expect(cast_body, "B's copy of A casts it")


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


@session_scenario(starts=("entrance", "entrance"))
def pickup_icon_matches_for_both_players(run):
    """Issue 100: a pickup's icon loads when it starts, in the room's authority only. B arrives
    after it has, and still draws the same icon (not whatever was in that slot)."""
    from session_progress import HOLY_MAIL, NO3
    a, b = run.s.a, run.s.b
    room, x, y = HOLY_MAIL
    before = icons(b)
    arrive(run, a, NO3, room, x - 48, y - 40)
    run.step(60)
    run.expect(icons(a) != before, "A loaded the icon")
    run.expect(icons(b) != icons(a), "B hasn't got it yet")
    arrive(run, b, NO3, room, x - 48, y - 40)
    for t in range(600):
        run.step(1)
        roles = (a.mailbox("self_presence").role, b.mailbox("self_presence").role)
        if roles == (1, 2):
            break
    run.expect(roles == (1, 2), "A runs the room, B is the guest", roles=roles, a=a.snapshot(), b=b.snapshot())
    run.step(90)  # an icon a frame
    run.expect(icons(a) == icons(b), "both have the same icon, tiles and palette")


@session_scenario(starts=("entrance", "entrance"))
def pickup_name_shows_for_both_players(run):
    """Report 222025: B gets what A picked up, and now sees its name too."""
    from session_progress import HOLY_MAIL, counts, take
    a, b = run.s.a, run.s.b
    run.expect(not b.read(BOTTOM_TEXT_TIMER, "<i"), "B has no text up")
    take(run, a, HOLY_MAIL, frames=20)
    shown = 0
    for t in range(300):
        run.step(1)
        shown = shown or b.read(BOTTOM_TEXT_TIMER, "<i")
    run.expect(shown, "the name came up in B's game too")


def symbols_status(g):
    return g.addr("g_Status") + 0x23C


@session_scenario(starts=(MARBLE, MARBLE))
def crashwatch_pause_menu_is_not_a_hang(run):
    """Issues 150 and 152 (0.16.0): 10 s in the pause or equip menu was taken for a hang, and
    the game went back to the menu (online, the partner saw a disconnect)."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
    import crashwatch
    from link.mailbox import PAUSED
    a = run.s.a
    run.step(60)
    run.step(2, ("start", ""))
    run.step(60)
    p = a.mailbox("self_presence")
    run.expect(p.flags & PAUSED, "the pause menu is open", flags=p.flags)
    watch, frame, beat, why = crashwatch.CrashWatch(), p.frame, a.mailbox("heartbeat"), None
    for _ in range(15):
        run.step(crashwatch.EVERY)
        why = why or watch.check(run.s.games)
    run.expect(a.mailbox("self_presence").frame == frame and a.mailbox("heartbeat") != beat,
               "in the menu the game's timer stops and its main loop runs",
               frame=(frame, a.mailbox("self_presence").frame), beat=(beat, a.mailbox("heartbeat")))
    run.expect(why is None, "15 s in the pause menu isn't a hang", why=why)


@session_scenario(starts=(MARBLE, MARBLE))
def partner_pad_quiet_in_menus(run):
    """Issue 151 (0.16.0): the buttons sent for the partner's copy of this player are the ones
    moving the player: none while the pause menu is open (the copy walked as they browsed)."""
    from link.mailbox import PAUSED
    a = run.s.a
    run.step(60, ("right", ""))
    run.expect(a.mailbox("self_presence").pad != 0, "in play, holding right is sent")
    run.step(2, ("start", ""))
    run.step(60)
    run.expect(a.mailbox("self_presence").flags & PAUSED, "the pause menu is open")
    pads = []
    for pad in ("right", "left", "down", "cross", "up"):
        run.step(10, (pad, ""))
        pads.append(a.mailbox("self_presence").pad)
    run.expect(pads == [0] * 5, "in the menu, nothing is sent", pads=pads)



EQUIPPED_WEAPON_IDS = 0x8003C90C  # g_EquippedWeaponIds (main.exe)
EQUIPMENT = 0x80097C00            # g_Status.equipment: the hands
WEAPON_PRG = (0x8017A000, 0x8017D000)
LAB = str(TOOLS["out"].parent / "fixtures" / "debug-starts" / "Alchemy Laboratory.state")
# What report 20261104-104320's Maria game had at 0x8017A000: no overlay, old data
LEFTOVER = bytes.fromhex("0200ed04 0e023e00 e22f2cf1 10fd0110 02000f00 3d1fffe3 001f0f2f 00de352c"
                         "0200cf03 e1501c1e e25ca340 002ce0f0 02001629 02ee53fc d2201f2f 0df220fe")


def _unpause_with_no_weapons_loaded(run, character):
    """Report 20261104-104320 (0.16.0, couch): Maria, both hands empty, paused and unpaused, and
    her game jumped to 0x2F0F1F00. After a load the game leaves the weapon overlays out for her
    and Richter, and the menu loads none for an empty hand, but its exit calls GetWeaponId
    through the right hand's table: whatever that memory last held."""
    a = run.s.a
    run.step(30)
    a.write(EQUIPMENT, 0)
    a.write(EQUIPMENT + 4, 0)
    run.expect(reload_game(run, a), "Continue's load brings this game's player in")
    for hand in (0, 1):  # what the report's game had there: old data, no overlay
        a.write_bytes(WEAPON_PRG[hand], LEFTOVER)
    run.step(60)
    p = a.mailbox("self_presence")
    ids = [a.read(EQUIPPED_WEAPON_IDS + 4 * h, "<i") for h in (0, 1)]
    run.expect(p.character == character and ids == [-1, -1], "the load left the weapons out",
               character=p.character, ids=ids)
    tables = [a.read_bytes(WEAPON_PRG[h], len(LEFTOVER)) for h in (0, 1)]
    run.expect(LEFTOVER not in tables, "the module put a table there that does nothing")
    for button, frames, gap in (("start", 7, 25), ("cross", 8, 61), ("down", 2, 6),
                                ("triangle", 7, 6), ("triangle", 5, 8), ("triangle", 5, 47)):
        run.step(frames, (button, ""))  # the report's presses: Start, Cross, Down, Triangle x3
        run.step(gap)
    beat, frame = a.mailbox("heartbeat"), a.mailbox("self_presence").frame
    run.step(300)
    p = a.mailbox("self_presence")
    run.expect(a.mailbox("heartbeat") != beat, "the main loop runs after unpausing",
               beat=(beat, a.mailbox("heartbeat")))
    run.expect(p.frame != frame and not p.flags & PAUSED, "the game's timer runs after unpausing",
               frame=(frame, p.frame), flags=p.flags)


@session_scenario(starts=(LAB, LAB), characters=(2, 0))
def unpause_with_empty_hands_maria_and_alucard(run):
    _unpause_with_no_weapons_loaded(run, 2)


@session_scenario(starts=(LAB, LAB), characters=(1, 0), full=True)
def unpause_with_empty_hands_richter_and_alucard(run):
    _unpause_with_no_weapons_loaded(run, 1)


SPELL_HELLFIRE_STEP = 34  # Player_SpellHellfire (include/player_steps.h)


@session_scenario(starts=(MARBLE, MARBLE), characters=(0, 0))
def spell_by_hand_with_partner_near(run):
    """Issue 167: A types Hellfire's own inputs (up, down, down-forward, forward, attack), each
    held 1 to 3 frames as a player's thumb does, while B, in the same room, stands or walks. The
    partner's body runs Alucard's input code in A's game too: it mustn't spoil A's sequence."""
    from scenarios_m8 import MP, MP_MAX, SPELLS_LEARNT
    a, b = run.s.a, run.s.b
    for g in (a, b):
        g.write(SPELLS_LEARNT, 0xFF)
    run.step(60, ("right", ""))  # A faces right: forward is right
    run.step(30)
    missed = []
    for b_pad in ("", "left", "right+square"):
        for hold in (1, 2, 3):
            for g in (a, b):
                g.write(MP, 99, "<i")
                g.write(MP_MAX, 99, "<i")
            seq = [p for p in ("up", "down", "down+right", "right", "square") for _ in range(hold)]
            cast = False
            for t in range(len(seq) + 30):
                run.step(1, (seq[t] if t < len(seq) else "", b_pad))
                cast |= a.read(a.entity(0) + PLAYER_STEP, "<H") == SPELL_HELLFIRE_STEP
            if not cast:
                missed.append((b_pad or "idle", hold))
            run.step(150, ("", b_pad))  # the spell ends
            run.step(60, ("right", ""))  # facing right again
    run.expect(not missed, "A's Hellfire comes out every time, whatever B does", missed=missed)


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
