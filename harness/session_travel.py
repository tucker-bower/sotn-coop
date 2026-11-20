"""M3 acceptance tests: teleport, respawn, pause rules, joint save (design/M3-teleport-respawn-save.md)."""


from session import Session, session_scenario  # first: puts `link` on the path

from bots import walker
from link.mailbox import BUSY, DEAD, IN_PLAY
from lockstep import random_inputs
from session_progress import arrive

STAGES = ("entrance", "nz0", "no0", "no1")
ENGINE_NORMAL, ENGINE_MENU, ENGINE_MAP = 1, 2, 20
GAME_PLAY, GAME_OVER = 2, 3


def wait_arrived(run, g, target, limit=600):
    """Steps until g is in play, not busy, in target's (stage, room). Returns frames, or None."""
    for i in range(limit):
        run.step(1)
        p = g.mailbox("self_presence")
        if p.room == target.room and p.flags & IN_PLAY and not p.flags & BUSY:
            return i
    return None


def map_teleport(run, g):
    """Opens g's map, presses ✕ (port 1 of g)."""
    pads = lambda pad: ("", pad) if g is run.s.b else (pad, "")
    run.step(1, p1=pads("select"))
    run.step(40)
    run.step(1, p1=pads("cross"))


@session_scenario(starts=("entrance", "nz0"))
def teleport_to_partner_with_another_stage_id(run):
    """Issue 179: the randomizer's 2nd-castle start sets g_StageId to RNO0 (0x20) on the
    entrance's trap door while the player stays in NO3. A partner who map-teleported there loaded
    the inverted Marble Gallery. Presence now says the stage that's loaded, and the partner lands
    next to the player."""
    a, b = run.s.a, run.s.b
    run.step(60)
    there = a.mailbox("self_presence")
    a.write("g_StageId", 0x20)  # what the trap door's patch does
    run.step(10)
    run.expect(a.mailbox("self_presence").stage == there.stage, "A still says the stage it's in",
               said=hex(a.mailbox("self_presence").stage), loaded=hex(there.stage))
    map_teleport(run, b)
    frames = wait_arrived(run, b, there, 900)
    p = b.mailbox("self_presence")
    run.expect(frames is not None, "B lands in A's room, not the inverted castle", b=(hex(p.stage), p.room_id),
               a=(hex(there.stage), there.room_id))


@session_scenario(starts=("entrance", "nz0"))
def teleport_partner_busy(run):
    """M3 criterion 3: while A is loading (A itself arriving somewhere), ✕ on B's map does nothing."""
    from link.mailbox import CMD_ARRIVE
    a, b = run.s.a, run.s.b
    run.step(300)
    room0 = b.mailbox("self_presence").room
    run.step(1, p1=("", "select"))
    run.step(40)
    p = b.mailbox("self_presence")
    a.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)  # A starts loading
    for _ in range(3):
        run.step(1)
        if a.mailbox("self_presence").flags & BUSY:
            break
    run.expect(a.mailbox("self_presence").flags & BUSY, "A is busy (loading)")
    run.step(1, p1=("", "cross"))
    run.step(240)
    run.expect(b.mailbox("self_presence").room == room0, "B stayed where it was")


def die(run, g, limit=4000):
    """Harness: HP 1, then walk g into the entrance hall's zombies until the death sequence."""
    g.write("g_Status", 1, "<i", 0x23C)
    bot = walker("left", attack_every=0)
    for i in range(limit):
        pad = bot(g.snapshot(), i)
        run.step(1, p1=(pad, "") if g is run.s.a else ("", pad))
        if g.mailbox("self_presence").flags & DEAD or g.read("g_GameEngineStep") == 10:
            return i
    return None


def chaos(run, minutes):
    """M3 criterion 8: both games mash buttons; every 10 s one of them teleports to the other,
    and every 30 s one is dropped to 1 HP (so deaths and respawns happen). No crash, both end in
    play, and the shared state converges."""
    from link.mailbox import CMD_ARRIVE
    from session_scenarios import assert_converged
    import random
    a, b = run.s.a, run.s.b
    rng = random.Random(9)
    frames = int(minutes * 3600)
    ia, ib = list(random_inputs(31, frames)), list(random_inputs(32, frames))
    teleports = deaths = 0
    for t in range(0, frames, 600):
        run.step(600, p1=lambda i, sa, sb, t=t: (ia[t + i][0], ib[t + i][0]))
        g, other = (a, b) if rng.random() < 0.5 else (b, a)
        p = other.mailbox("self_presence")
        if p.flags & IN_PLAY and not p.flags & (BUSY | DEAD):
            g.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)
            teleports += 1
        if (t // 600) % 3 == 2:
            g.write("g_Status", 1, "<i", 0x23C)
            deaths += 1
        for x in (a, b):
            if x.read("g_GameState") == GAME_OVER:
                run.expect(False, f"game {x.name} reached Game Over", t=t)
    run.step(300)
    run.expect(a.snapshot()["game_state"] == GAME_PLAY and b.snapshot()["game_state"] == GAME_PLAY,
               "both still in play", a=a.snapshot(), b=b.snapshot(), teleports=teleports, low_hp=deaths)
    assert_converged(run)


WRP, WRP_OUTER_WALL = 0x0E, 16  # the warp rooms' stage; its room at the Outer Wall (59,17)


@session_scenario(starts=("no1", "no1"))
def teleport_to_partner_in_warp_room(run):
    """#289 (1.1.1 playtest): A is in a warp room (a stage of its own, WRP), B teleports to A from
    the map, and lands there in play. Twice, B's game hung on a garbled screen."""
    a, b = run.s.a, run.s.b
    run.step(120)
    arrive(run, a, WRP, WRP_OUTER_WALL, 150, 167)
    run.step(60)
    target = a.mailbox("self_presence")
    map_teleport(run, b)
    frames = wait_arrived(run, b, target, 900)
    p = b.mailbox("self_presence")
    run.expect(frames is not None, "B lands in A's warp room, in play", b=str(p), a=str(target))
    run.step(120)
    p = b.mailbox("self_presence")
    run.expect(p.flags & IN_PLAY and not p.flags & BUSY and p.room == target.room, "and stays there", b=str(p))


NO1, NO1_BY_WARP = 0x01, 0  # the Outer Wall's room (60,17): its left door leads to the warp room


def _into_warp_room(run, partner_where):
    """A walks through the Outer Wall's door into its warp room, with B there already or beside A."""
    a, b = run.s.a, run.s.b
    run.step(120)
    arrive(run, a, NO1, NO1_BY_WARP, 180, 135)
    if partner_where == "warp":
        arrive(run, b, WRP, WRP_OUTER_WALL, 150, 167)
    else:
        arrive(run, b, NO1, NO1_BY_WARP, 150, 135)
    run.step(60)
    for i in range(900):
        run.step(1, p1=("left", ""))
        p = a.mailbox("self_presence")
        if p.stage == WRP and p.flags & IN_PLAY and not p.flags & BUSY and i > 30:
            break
    p = a.mailbox("self_presence")
    run.expect(p.stage == WRP and p.flags & IN_PLAY and not p.flags & BUSY, "A walks into the warp room, in play",
               a=str(p), b=str(b.mailbox("self_presence")))
    run.step(180)
    p = a.mailbox("self_presence")
    run.expect(p.stage == WRP and p.flags & IN_PLAY and not p.flags & BUSY, "and plays on there", a=str(p))


@session_scenario(starts=("no1", "no1"))
def warp_room_door_with_partner_inside(run):
    """#289 (1.1.1 playtest, report 161112): B is in the warp room; A walks in through its door.
    A's game hung, busy, on a garbled screen."""
    _into_warp_room(run, "warp")


@session_scenario(starts=("no1", "no1"))
def warp_room_door_with_partner_beside(run):
    """#289 (report 160825): A and B in the room by the warp room; A walks in through its door."""
    _into_warp_room(run, "beside")


def _press_up(run, g):
    pads = lambda pad: ("", pad) if g is run.s.b else (pad, "")
    run.step(1, p1=pads("up"))
    run.step(1)


@session_scenario(starts=("no1", "no1"))
def warp_with_partner_in_the_warp_room(run):
    """#290 (1.1.1 playtest, reports 161209 and 161217): both players stand on the Outer Wall's warp.
    Only the authority's warp ran: the guest's was a copy, so its Up did nothing, and it showed the
    authority's fade to white, which stayed when the authority left. Here the guest warps (to the
    Entrance's: its bit is always on), the other follows, then in the Entrance's warp room, shared
    again, the authority warps back. Each lands in play, faded back in, and whoever stays behind
    isn't left on a white screen."""
    from link.mailbox import ROLE_AUTHORITY, ROLE_GUEST
    a, b = run.s.a, run.s.b
    run.step(120)
    arrive(run, a, WRP, WRP_OUTER_WALL, 128, 167)
    run.step(30)
    arrive(run, b, WRP, WRP_OUTER_WALL, 128, 167)
    run.step(240)
    for n, who in enumerate((ROLE_GUEST, None, ROLE_AUTHORITY)):
        roles = {g.mailbox("self_presence").role: g for g in (a, b)}
        if who is None:  # the one still in the Outer Wall's warp room
            g = next(g for g in (a, b) if g.mailbox("self_presence").room_id == WRP_OUTER_WALL)
            name, other = "the one left behind", None
        else:
            run.expect(set(roles) == {ROLE_AUTHORITY, ROLE_GUEST}, f"warp {n + 1}: the warp room is shared",
                       roles=sorted(roles))
            g = roles[who]
            other = roles[ROLE_AUTHORITY if who == ROLE_GUEST else ROLE_GUEST]
            name = "the guest" if who == ROLE_GUEST else "the authority"
        before = g.mailbox("self_presence")
        _press_up(run, g)
        moved = None
        for i in range(900):
            run.step(1)
            p = g.mailbox("self_presence")
            if p.room != before.room and p.flags & IN_PLAY and not p.flags & BUSY:
                moved = i
                break
        p = g.mailbox("self_presence")
        run.expect(moved is not None, f"warp {n + 1}: {name} warps out, in play", p=str(p), before=str(before))
        run.step(240)
        p = g.mailbox("self_presence")
        run.expect(p.stage == WRP and p.flags & IN_PLAY and not p.flags & BUSY and g.read("g_PauseAllowed"),
                   f"...and plays on in the next warp room, faded back in", p=str(p))
        run.capture()
        if other:
            shot = other.screenshot().convert("L")
            bright = sum(shot.getdata()) / (shot.width * shot.height)
            run.expect(bright < 160, "...and the partner left behind isn't on a white screen", brightness=round(bright))


BOTTOM_TEXT_TIMER = 0x80097410  # g_unkGraphicsStruct.BottomCornerTextTimer


@session_scenario(starts=("entrance", "nz0"))
def map_shows_the_teleport_prompt(run):
    """Tucker (1.3.0): the map screen says what ✕ does. With the partner in reach, opening the map
    shows "✕ Go to partner" in the game's text box; closing it takes it away."""
    a = run.s.a
    run.step(120)
    run.expect(not a.read(BOTTOM_TEXT_TIMER, "<i"), "no prompt in play")
    run.step(1, ("select", ""))
    run.step(40)
    shown = a.read(BOTTOM_TEXT_TIMER, "<i")
    run.capture()
    run.expect(shown, "the map shows the prompt", timer=shown)
    run.step(1, ("select", ""))
    run.step(40)
    run.expect(not a.read(BOTTOM_TEXT_TIMER, "<i"), "closing the map takes it away")
