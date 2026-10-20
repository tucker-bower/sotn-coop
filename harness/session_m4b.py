"""M4b: fixes from playtest 1 (docs/playtest_notes/playtest_1.md, design/M4b-playtest-fixes.md)."""

import struct

from session import Session, SessionRun, session_scenario  # first: puts `link` on the path

from link.mailbox import CONTROL_MUTE_MUSIC, ROLE_AUTHORITY, ROLE_GUEST
from module import COOP_DISC
from session_progress import status


def roles(s):
    return s.a.mailbox("self_presence").role, s.b.mailbox("self_presence").role


def screen_diff(x, y, mask=None):
    """Pixels that differ between two screenshots (any channel by more than 8), outside mask
    (a box: left, top, right, bottom)."""
    from PIL import ImageChops
    d = ImageChops.difference(x.convert("RGB"), y.convert("RGB")).convert("L").point(lambda v: 255 if v > 8 else 0)
    if mask:
        d.paste(0, mask)
    return sum(1 for v in d.get_flattened_data() if v) if hasattr(d, "get_flattened_data") else \
        sum(1 for v in d.getdata() if v)


def jump_frames(linked, frames=(10, 20, 30, 40)):
    """B jumps at the castle entrance while A stands still. Returns B's screenshots at those
    frames, and where A's sprite is on B's screen."""
    with Session(COOP_DISC) as s:
        if not linked:
            s.a.unlink(), s.b.unlink()
        s.step(120)
        shared = roles(s)
        shots, where = {}, {}
        for i in range(max(frames) + 1):
            s.step(1, ("", "cross"))
            if i in frames:
                shots[i] = s.b.screenshot()
                p = s.a.mailbox("self_presence")
                where[i] = (p.x - s.b.read("g_Tilemap", "<h", 0xA), p.y - s.b.read("g_Tilemap", "<h", 0xE))
        return shots, where, shared


@session_scenario()
def guest_scenery_matches_solo(run):
    """Playtest 1, #1: on the guest's screen, the scenery (trees, bushes) is where the guest's own
    game would draw it. B jumps (its camera moves away from A's); B's screen, shared, matches B's
    screen playing alone, except around A's sprite."""
    linked, where, shared = jump_frames(True)
    solo, _, _ = jump_frames(False)
    run.expect(shared == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B the guest", roles=shared)
    for i, shot in linked.items():
        x, y = where[i]
        n = screen_diff(shot, solo[i], (x - 40, y - 56, x + 40, y + 56))
        run.expect(n < 50, f"frame {i}: B's screen matches its solo screen (outside A's sprite)", differing=n)


def sound_level(g, frames):
    """Mean absolute sample over these frames of B's sound."""
    from array import array
    total = count = 0
    for _ in range(frames):
        _, sound = g.frame(0)
        a = array("h", sound[:len(sound) // 2 * 2])
        total += sum(abs(v) for v in a)
        count += len(a)
    return total / max(count, 1)


@session_scenario(starts=(None, None))
def music_mute(run):
    """Couch play: only one game plays music. With CONTROL_MUTE_MUSIC the Alchemy Lab's music goes
    silent, and comes back when it's cleared. (Not the entrance: its thunder is a sound effect.)"""
    with Session(COOP_DISC, starts=("nz0", "nz0"), audio=True) as s:
        a = s.a
        sound_level(a, 120)
        loud = sound_level(a, 180)
        a.mailbox("set_control", CONTROL_MUTE_MUSIC)
        sound_level(a, 10)
        quiet = sound_level(a, 180)
        a.mailbox("set_control", 0)
        sound_level(a, 30)
        back = sound_level(a, 180)
        run.expect(loud > 100, "music plays", level=round(loud))
        run.expect(quiet < loud / 10, "muted: (almost) silent", level=round(quiet), music=round(loud))
        run.expect(back > loud / 2, "unmuted: the music is back", level=round(back), music=round(loud))


@session_scenario()
def hand_over_keeps_dead_dead(run):
    """Playtest 1, #1: B (the guest) kills the hall's Warg; A (the authority) walks far away, so B
    takes the hall over; B roams the hall, now running it itself. The Warg stays dead (it came back before: the layout spawner
    resumed from where the authority's camera had been)."""
    from session_shared import WARG_SLOT, into_hall, stage_entities
    from bots import walker
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.expect(roles(run.s) == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B the guest", roles=roles(run.s))
    warg = stage_entities(a)[WARG_SLOT][0]
    a.write(a.entity(WARG_SLOT), 1, "<h", 0x3E)  # one hit from death (harness shortcut)
    bot = walker("left", attack_every=6)
    for i in range(900):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        if stage_entities(a).get(WARG_SLOT, (0,))[0] != warg:
            break
    run.expect(stage_entities(a).get(WARG_SLOT, (0,))[0] != warg, "B killed the Warg", frames=i)
    run.step(60)
    out = walker("left", attack_every=8)
    from session_scenarios import heal
    for i in range(3000):  # the authority walks away until the cameras part (as in the playtest)
        run.step(1, p1=(out(a.snapshot(), i), ""))
        if i % 20 == 0:
            heal(a), heal(b)  # the hall's enemies would kill them on the way
        if roles(run.s) == (0, 0):
            break
    run.step(60, p1=("left", ""))
    run.expect(roles(run.s) == (0, 0), "A walked away: B runs the hall itself", frames=i)
    seen = []
    for direction, n in (("left", 200), ("right", 400), ("left", 400), ("right", 200)):
        for _ in range(n):
            run.step(1, p1=("", direction))
            if _ % 20 == 0:
                heal(b)
            seen += [s for s, e in stage_entities(b).items() if s == WARG_SLOT and e[0] == warg]
    run.expect(not seen, "the Warg didn't come back while B roamed the hall", slots=sorted(set(seen)))


LCK_TOTAL = 0x80097BE4   # g_Status.statsTotal[STAT_LCK]
LCK_BASE = 0x80097BC4    # g_Status.statsBase[STAT_LCK]: the game recomputes the total from it


def lucky(g):
    g.write(LCK_BASE, 4000, "<i")
    g.write(LCK_TOTAL, 4000, "<i")
E_PRIZE_DROP_NO3 = 0x03  # NO3's entity id for money/heart drops


def drops(g):
    import struct
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    return {s for s in range(160, 192) if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0] == E_PRIZE_DROP_NO3}


@session_scenario()
def guest_kill_drops(run):
    """Playtest 1, #1: the guest kills the Warg (with luck so high that every kill drops). The
    drop the guest's kill rolled appears in the authority's world, and from there on the guest's
    screen too. (It used to vanish: only the guest's game ran the kill, and the next snapshot
    wiped what it created.)"""
    from session_shared import WARG_SLOT, into_hall, stage_entities
    from session_scenarios import heal
    from bots import walker
    a, b = run.s.a, run.s.b
    into_hall(run)
    lucky(b)
    warg = stage_entities(a)[WARG_SLOT][0]
    before = drops(a)
    bot = walker("left", attack_every=6)
    for i in range(900):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        if i % 20 == 0:
            heal(a), heal(b)
        if stage_entities(a).get(WARG_SLOT, (0,))[0] != warg:
            break
    run.expect(stage_entities(a).get(WARG_SLOT, (0,))[0] != warg, "B killed the Warg", frames=i)
    new = drops(a) - before
    for _ in range(10):  # B steps back: touching the drop collects it (D66)
        run.step(1, p1=("", "right"))
        new |= drops(a) - before
    run.expect(new, "a drop appeared in A's world", slots=sorted(new))
    run.step(4, p1=("", "right"))
    run.expect(drops(b) & drops(a), "and on B's screen", a=sorted(drops(a)), b=sorted(drops(b)))


TEXT_TIMER = 0x80097410  # g_unkGraphicsStruct.BottomCornerTextTimer: the text box is up


def brightness(img):
    return sum(img.convert("L").get_flattened_data()) / (img.width * img.height)


@session_scenario(starts=("entrance", "nz0"))
def teleport_flash_and_text(run):
    """Playtest 1, #2: B teleports to A from the map. On arrival the screen flashes (Richter's
    Cross Crash fade) and the text box says so."""
    from session_travel import map_teleport, wait_arrived
    a, b = run.s.a, run.s.b
    run.step(60)
    map_teleport(run, b)
    t = wait_arrived(run, b, a.mailbox("self_presence"))
    run.expect(t is not None, "B arrived at A", frames=t)
    shown, light = False, []
    for i in range(120):  # the flash: up to white in about half a second, then back down
        run.step(1)
        shown |= b.read(TEXT_TIMER) > 0
        if i % 6 == 0:
            light.append(brightness(b.screenshot()))
    run.expect(shown, "the text box came up on B's screen")
    peak = light.index(max(light))
    run.expect(max(light) > 180 and light[-1] < max(light) - 60 and 0 < peak < len(light) - 1,
               "the screen flashed white, then cleared", brightness=[round(x) for x in light])


@session_scenario(starts=("entrance", "nz0"))
def death_fades_out(run):
    """Playtest 1, #2: when A dies, its screen fades to black before it respawns at B (it used to
    cut straight to the load, which looked like a freeze); on arrival the text box says why."""
    from session_travel import die
    a, b = run.s.a, run.s.b
    run.step(300)
    t = die(run, a)
    run.expect(t is not None, "A died", frames=t)
    dark, text = None, False
    for i in range(900):
        run.step(1)
        if i % 4 == 0 and dark is None and a.read("g_GameEngineStep") == 10:
            if brightness(a.screenshot()) < 4:
                dark = i
        text |= a.read(TEXT_TIMER) > 0
        p = a.mailbox("self_presence")
        if text and p.room == b.mailbox("self_presence").room:
            break
    run.expect(dark is not None and dark > 30, "A's screen faded to black first", frame=dark)
    run.expect(text, "and after respawning at B, the text box came up")


@session_scenario(starts=("nz0", "entrance"))
def partner_save_text(run):
    """Playtest 1, #3: A saves in a save room's coffin; B's game freezes while it writes its own
    card. B's text box says why while it's frozen, then that the game was saved."""
    import tempfile
    from pathlib import Path
    from session_saverooms import COFFIN, NZ0, SAVE_ROOM
    from session_progress import arrive
    path = Path(tempfile.mkdtemp(prefix="coop-m4b-")) / "session.coop"
    with Session(COOP_DISC, starts=("nz0", "entrance"), session_file=path) as s:
        sub = SessionRun(s, run.name)
        a, b = s.a, s.b
        arrive(sub, a, NZ0, SAVE_ROOM, *COFFIN)
        sub.step(60)
        sub.step(2, p1=("up", ""))
        frozen_with_text = frozen = 0
        after = False
        for i in range(900):
            t = b.read("g_Timer")
            sub.step(1)
            if b.read("g_Timer") == t:
                frozen += 1
                frozen_with_text += b.read(TEXT_TIMER) > 0
            elif frozen and b.read(TEXT_TIMER) > 0:
                after = True
            if b.mailbox("card_result") and after:
                break
        run.expect(frozen > 0, "B froze while saving", frames=frozen)
        run.expect(frozen_with_text >= frozen - 2, "with the text box up", frozen=frozen, with_text=frozen_with_text)
        run.expect(after, "and the text box was up after it, too")


@session_scenario()
def guest_hit_flashes(run):
    """Playtest 1, #1: an enemy the guest hits flashes, as it does when the authority hits it
    (the rainbow flash is the game's own; guest hits didn't start it at all)."""
    import struct
    from session_shared import WARG_SLOT, into_hall, stage_entities
    from session_scenarios import heal
    from bots import walker
    a, b = run.s.a, run.s.b
    into_hall(run)
    hp0 = stage_entities(a)[WARG_SLOT][3]
    flags = lambda g: struct.unpack_from("<I", g.read_bytes(g.entity(WARG_SLOT), 0xBC), 0x34)[0]
    bot = walker("left", attack_every=6)
    for i in range(600):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        if i % 20 == 0:
            heal(a), heal(b)
        if stage_entities(a)[WARG_SLOT][3] < hp0:
            break
    run.expect(stage_entities(a)[WARG_SLOT][3] < hp0, "B hit the Warg", frames=i)
    flash_a = flash_b = False
    for _ in range(4):
        flash_a |= (flags(a) & 0xF) != 0
        flash_b |= (flags(b) & 0xF) != 0
        run.step(1)
    run.expect(flash_a, "it flashes in A's world")
    run.expect(flash_b, "and on B's screen")


CANDLE_SLOT, CANDLE_X = 71, 1248  # a wall candle in the entrance hall (layout entry)


@session_scenario()
def guest_breaks_candle(run):
    """Playtest 1, #1: the guest breaks a wall candle: it breaks in the authority's world (and so
    on both screens), as it does when the authority breaks one. (Candles react to the hit's
    hitParams, which guest hits didn't carry.)"""
    import struct
    from session_progress import arrive
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    into_hall(run)
    p = a.mailbox("self_presence")
    candle = lambda g: struct.unpack_from("<H", g.read_bytes(g.entity(CANDLE_SLOT), 0xBC), 0x26)[0]
    run.expect(candle(a) and candle(b), "the candle is there in both worlds")
    arrive(run, b, p.stage, p.room_id, CANDLE_X, p.ground_y)
    run.step(30)
    run.expect(roles(run.s) == (ROLE_AUTHORITY, ROLE_GUEST), "B is A's guest", roles=roles(run.s))
    for _ in range(8):  # jump attacks
        run.step(8, p1=("", "cross"))
        run.step(4, p1=("", "cross+square"))
        run.step(30)
        if not candle(a):
            break
    run.step(10)
    run.expect(not candle(a), "the candle broke in A's world")
    run.expect(not candle(b), "and on B's screen")


PRIM_ENV, POOL, POOL_N, DR_ENV_SIZE = 7, 0x800974AC, 16, 0x40  # DRA's DR_ENV pool (D_800974AC)


def env_prims(g, slots=range(64, 256)):
    """{slot: [(r1 pointer, DR_ENV bytes)]} for the PRIM_ENV primitives each entity draws with."""
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    out = {}
    for slot in slots:
        e = raw[slot * 0xBC:(slot + 1) * 0xBC]
        if not struct.unpack_from("<H", e, 0x26)[0] or not struct.unpack_from("<I", e, 0x34)[0] & 0x800000:
            continue
        p = g.addr("g_PrimBuf") + struct.unpack_from("<i", e, 0x64)[0] * 0x34
        envs = []
        for _ in range(64):
            prim = g.read_bytes(p, 0x34)
            if prim[7] == PRIM_ENV:
                ptr = struct.unpack_from("<I", prim, 0x10)[0]
                envs.append((ptr, g.read_bytes(ptr, DR_ENV_SIZE) if POOL <= ptr < POOL + POOL_N * DR_ENV_SIZE else b""))
            p = struct.unpack_from("<I", prim, 0)[0]
            if not p:
                break
        if envs:
            out[slot] = envs
    return out


@session_scenario()
def guest_sees_warg_death(run):
    """Playtest 1, #1 ("a visual glitch when a monster we both hit died"): the Warg burns away
    with a render-to-texture effect: PRIM_ENV primitives, each with a DR_ENV from DRA's pool. The
    guest used to copy the authority's DR_ENV pointers, which point at its own, unrelated pool
    entries: its screen showed leftover VRAM (a piece of the HUD). Now each mirrored PRIM_ENV has a
    pool entry of the guest's own, with the authority's contents."""
    from session_shared import WARG_SLOT, into_hall, stage_entities
    from session_scenarios import heal
    a, b = run.s.a, run.s.b
    into_hall(run)
    warg = stage_entities(a)[WARG_SLOT][0]
    a.write(a.entity(WARG_SLOT), 1, "<h", 0x3E)
    checked = bad = 0
    before = {}  # A's last frame: the guest shows the authority's previous frame
    for i in range(1500):  # both stand together; B punches the Warg when it comes
        run.step(1, p1=("", "left+square" if i % 12 < 2 else ""))
        if i % 20 == 0:
            heal(a), heal(b)
        ea, eb = env_prims(a), env_prims(b)
        for slot, envs in before.items():
            checked += 1
            mine = eb.get(slot, [])
            own = [ptr for ptr, _ in mine]
            # Each its own valid pool entry; the first (the render-to-texture pass) with A's
            # contents. The others are switched back to the frame buffer by the renderer itself.
            if len(mine) != len(envs) or len(set(own)) != len(own) or any(not d for _, d in mine) or \
                    mine[0][1] != envs[0][1]:
                bad += 1
        before = ea
        if stage_entities(a).get(WARG_SLOT, (0,))[0] != warg and i > 60 and checked and not ea:
            break
    run.expect(stage_entities(a).get(WARG_SLOT, (0,))[0] != warg, "B killed the Warg", frames=i)
    run.expect(checked > 0, "its burning (PRIM_ENV) reached B's world", frames_checked=checked)
    # The frame the effect starts can differ (its first pass is set up and drawn in one frame).
    run.expect(bad <= 2, "every mirrored PRIM_ENV has its own pool entry, with A's contents", bad=bad,
               of=checked)


@session_scenario()
def guest_sees_pickup_text(run):
    """A relic's "Obtained ..." box is drawn from text the stage writes into VRAM as it runs. B
    (the authority) takes the Cube of Zoe; on A's screen (the guest) the box shows the same text
    (it was empty: the guest never made those VRAM uploads)."""
    from session_progress import CUBE_OF_ZOE, arrive
    a, b = run.s.a, run.s.b
    room, x, y = CUBE_OF_ZOE
    arrive(run, b, 0x41, room, x + 40, y)  # B first: B is the room's authority
    run.step(30)
    arrive(run, a, 0x41, room, x - 40, y)
    run.step(30)
    run.expect(roles(run.s) == (ROLE_GUEST, ROLE_AUTHORITY), "B is the authority, A its guest", roles=roles(run.s))
    shown, diffs = 0, []
    for i in range(240):
        run.step(1, p1=("", "left" if i < 30 else ""))
        if i % 6:
            continue
        box = (40, 196, 216, 216)
        cb = b.screenshot().crop(box).convert("L")
        bright_b = sum(1 for v in cb.get_flattened_data() if v > 150)
        if bright_b > 40:  # B's box shows text
            shown += 1
            ca = a.screenshot().crop(box).convert("L")
            diffs.append((sum(1 for v in ca.get_flattened_data() if v > 150), bright_b))
    run.expect(shown, "B's message box came up")
    # The cameras differ (the box is at the same place, the background behind it isn't): compare
    # the text, as bright pixels in the box, frame by frame.
    same = sum(1 for na, nb in diffs if abs(na - nb) <= nb // 5)
    run.expect(same >= len(diffs) * 3 // 4, "and A's shows the same text", frames_alike=same, of=len(diffs),
               sample=diffs[:5])




@session_scenario()
def guest_takes_heart(run):
    """D66 (was the known gap D51): a heart the guest picks up is the guest's. A large heart is
    dropped in the hall (harness: a prize drop entity made in A's world, as a kill makes one);
    B, the guest, walks over it: B's hearts go up, A's don't, and it's gone from both worlds."""
    from module import stage_symbol
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.expect(roles(run.s) == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B the guest", roles=roles(run.s))
    slot = next(k for k in range(160, 192) if not a.read(a.entity(k) + 0x26, "<H"))
    e = a.entity(slot)
    a.write_bytes(e, bytes(0xBC))
    a.write(e, E_PRIZE_DROP_NO3, "<H", 0x26)
    a.write(e, stage_symbol("stno3", "EntityPrizeDrop"), "<I", 0x28)
    a.write(e, 1, "<H", 0x30)  # params: ITEMDROP_LARGE_HEART
    drop_x = b.snapshot()["world_x"] + 40
    a.write(e, drop_x - a.read("g_Tilemap", "<h", 0xA), "<h", 2)
    a.write(e, b.snapshot()["world_y"] - 40 - a.read("g_Tilemap", "<h", 0xE), "<h", 6)
    hearts = lambda g: g.read("g_Status", "<i", 0x244)
    for g in (a, b):
        g.write("g_Status", 10, "<i", 0x244)
    run.step(60)  # it falls to the floor
    run.expect(slot in drops(a) and slot in drops(b), "the heart is there in both worlds")
    ha, hb = hearts(a), hearts(b)
    for i in range(300):
        run.step(1, p1=("", "right"))
        if hearts(b) != hb:
            break
    run.step(20)
    run.expect(hearts(b) > hb, "B's hearts went up", was=hb, now=hearts(b))
    run.expect(hearts(a) == ha, "A's didn't", was=ha, now=hearts(a))
    run.expect(slot not in drops(a) and slot not in drops(b), "the drop is gone from both worlds")


ELEVATOR_ROOM, ELEVATOR_SLOT, ELEVATOR_X, ELEVATOR_Y = 176, 96, 144, 96  # NZ0: a tall shaft


@session_scenario(starts=("nz0", "nz0"))
def guest_stands_on_elevator(run):
    """D52, fixed: an entity is solid because its update pushes the player out. The Alchemy Lab
    shaft's elevator is one. A (the authority) is in the shaft; B (the guest) drops onto the
    elevator and stands on it, instead of falling through to the bottom of the shaft."""
    from session_progress import arrive
    a, b = run.s.a, run.s.b
    arrive(run, a, 0x0C, ELEVATOR_ROOM, ELEVATOR_X - 40, ELEVATOR_Y - 60)
    run.step(60)
    arrive(run, b, 0x0C, ELEVATOR_ROOM, ELEVATOR_X, ELEVATOR_Y - 60)
    run.step(10)
    run.expect(roles(run.s) == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B the guest", roles=roles(run.s))
    top = lambda: struct.unpack_from("<h", a.read_bytes(a.entity(ELEVATOR_SLOT), 0xBC), 6)[0] + a.read("g_Tilemap", "<h", 0xE)
    ys = []
    for i in range(120):
        run.step(1)
        ys.append(b.snapshot()["world_y"])
    # A player's y is its middle, some 40 px above its feet; the shaft's bottom is 800 px down.
    run.expect(max(ys) < top() + 48 and ys[-1] == ys[-30], "B stands on the elevator (it didn't fall through)",
               b_y=ys[-1], lowest=max(ys), elevator=top())
