"""M1 acceptance tests that need two linked games (design/M1-link-presence.md)."""

import hashlib
from dataclasses import replace

from PIL import ImageChops

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from coop_env import DISKS
from link.mailbox import PARTNER_AGE
from lockstep import random_inputs
from module import COOP_DISC, symbols

RETAIL = DISKS / "sotn.us.cue"
# Game state the link must never change (criterion 8): every entity, the player, status, castle
# flags, the game's RNG, and the BIOS kernel area, which holds rand()'s seed.
STATE_REGIONS = [("g_Entities", 256 * 0xBC), ("g_Player", 0x3D0), ("g_Status", 0x334),
                 ("g_CastleFlags", 0x300), ("g_randomNext", 4), ("kernel", 0x10000)]
TCB_SIZE = 0xC0


def state_hash(g):
    """{region: sha1} over STATE_REGIONS. In the kernel area, the BIOS thread context (registers
    saved by the last interrupt) is zeroed: the module's extra instructions per frame move where
    VBlank interrupts the game, which is not game state."""
    out = {}
    for where, size in STATE_REGIONS:
        data = bytearray(g.read_bytes(0x80000000 if where == "kernel" else where, size))
        if where == "kernel":
            tcb = int.from_bytes(data[0x110:0x114], "little") & 0x1FFFFF  # BIOS table of TCBs
            data[tcb:tcb + TCB_SIZE] = bytes(TCB_SIZE)
        out[str(where)] = hashlib.sha1(data).hexdigest()[:12]
    return out


def scroll(g):
    return g.read("g_Tilemap", "<h", 0xA), g.read("g_Tilemap", "<h", 0xE)


def partner_pixels(g, frames=3):
    """What the partner adds to g's next frames: renders them with and without the partner
    (partnerAge pushed past the stale limit), then restores g. Returns (bbox, count, mean RGB).
    At least 2 frames: the screen shows the previous frame's image."""
    state = g.save_state()
    g.unlink()
    shots = []
    for show in (True, False):
        g.load_state(state)
        if not show:
            g.write(symbols()["g_CoopLink"] + PARTNER_AGE, 0xFFFF)
        g.step(frames)
        shots.append(g.screenshot())
    g.load_state(state)
    g.link()
    diff = ImageChops.difference(*shots)
    bbox = diff.getbbox()
    if not bbox:
        return None, 0, None
    px = [shots[0].getpixel((x, y)) for x in range(bbox[0], bbox[2]) for y in range(bbox[1], bbox[3])
          if diff.getpixel((x, y)) != (0, 0, 0)]
    return bbox, len(px), tuple(sum(c[i] for c in px) // len(px) for i in range(3))


@session_scenario(starts=("entrance", "entrance"), discs=(RETAIL, COOP_DISC))
def no_effect_on_play(run):
    """Criterion 3: with no partner, the co-op disc plays exactly like retail. The two entrance
    savestates come from separate boots (the co-op one also reads COOP.BIN), so their RNG and
    timers differ; game B therefore first takes game A's main RAM, keeping only its own hooked
    DRA instructions (the 5th, StoreSaveData, only runs at a save room). Then the walk_entrance_rooms route must match frame by frame."""
    a, b = run.s.a, run.s.b
    a.unlink(), b.unlink()
    ram_a, ram_b = bytearray(a.read_bytes(0x80000000, 2 << 20)), b.read_bytes(0x80000000, 2 << 20)
    # The hooks: `jal`s to CoopBoot and the 4 jump-table entries (module/dra_hooks.ld).
    targets = {0x801B9870, 0x80280000, 0x80280008, 0x80280010, 0x80280018}
    jals = {0x0C000000 | ((t & 0x3FFFFFF) >> 2) for t in targets}
    hooks = [i for i in range(0xA0000, 0x13B6A0, 4) if int.from_bytes(ram_b[i:i + 4], "little") in jals]
    run.expect(len(hooks) == 5 and all(ram_a[i:i + 4] != ram_b[i:i + 4] for i in hooks),
               "the co-op DRA has exactly 5 hook calls (one is the save room's), where retail calls the originals",
               hooks=[hex(0x80000000 + i) for i in hooks])
    for i in hooks:
        ram_a[i:i + 4] = ram_b[i:i + 4]
    b.write_bytes(0x80000000, bytes(ram_a))

    bots = walker("left", attack_every=8), walker("left", attack_every=8)
    diverged, rooms = [], []

    def each(i, sa, sb):
        ta = (sa["stage"], sa["room"], sa["world_x"], sa["world_y"], sa["hp"])
        tb = (sb["stage"], sb["room"], sb["world_x"], sb["world_y"], sb["hp"])
        if ta != tb and not diverged:
            diverged.append((i, ta, tb))
        if not rooms or rooms[-1] != sb["room"]:
            rooms.append(sb["room"])

    s0 = a.snapshot()
    run.step(3800, p1=lambda i, sa, sb: (bots[0](sa or s0, i), bots[1](sb or s0, i)), each=each)
    run.expect(not diverged, "retail and co-op disc match every frame", first_difference=diverged[:1])
    run.expect(rooms[-1] == (11, 40), "the co-op disc reaches the water room (11,40)", rooms=rooms)


@session_scenario()
def presence_follows(run):
    """Criterion 4: game A walks, jumps, crouches and turns. After every frame, B's mailbox holds
    A's presence from that same frame (so B draws it one frame later, A sees B's within two)."""
    a, b = run.s.a, run.s.b
    script = [("right", 60), ("right+cross", 20), ("right", 40), ("down", 30), ("", 10), ("left", 40),
              ("left+cross", 25), ("", 20)]
    seen = {"anim": set(), "flip": set(), "x": set()}
    mismatches = []
    for pad, n in script:
        for _ in range(n):
            run.step(1, p1=(pad, ""))
            mine, theirs = a.mailbox("self_presence"), b.mailbox("partner_presence")
            if mine != theirs:
                mismatches.append((pad, mine, theirs))
            seen["anim"].add(mine.anim_cur_frame), seen["flip"].add(mine.flip_x), seen["x"].add(mine.x)
    run.expect(not mismatches, "B's partner == A's presence after every frame (latency 1 frame)",
               mismatches=len(mismatches), first=str(mismatches[:1]))
    run.expect(len(seen["anim"]) > 10 and seen["flip"] == {0, 2} and len(seen["x"]) > 50,
               "the presence changed pose, facing and position", poses=len(seen["anim"]),
               flips=sorted(seen["flip"]), xs=len(seen["x"]))
    run.step(1)
    theirs, mine = a.mailbox("partner_presence"), b.mailbox("self_presence")
    run.expect(replace(theirs, frame=0) == replace(mine, frame=0) and mine.frame - theirs.frame == 1,
               "A holds B's presence from the previous frame (latency 2 frames)")
    run.expect(a.mailbox("partner_age") <= 1 and b.mailbox("partner_age") == 0, "both partners fresh",
               age_a=a.mailbox("partner_age"), age_b=b.mailbox("partner_age"))


@session_scenario()
def puppet_same_room_only(run):
    """Criterion 5: in the same room, each game draws the tinted partner where the partner really
    is; once A leaves the room, B draws nothing."""
    a, b = run.s.a, run.s.b
    run.step(90, p1=("", "right"))  # B moves away from A (both start on the same spot)
    for viewer, other in ((b, a), (a, b)):
        p = other.mailbox("self_presence")
        sx, sy = scroll(viewer)
        ex, ey = p.x - sx, p.y - sy
        bbox, count, rgb = partner_pixels(viewer)
        run.expect(bbox is not None and count > 150, f"game {viewer.name} draws its partner",
                   pixels=count, bbox=bbox)
        run.expect(bbox[0] - 8 <= ex <= bbox[2] + 8 and bbox[1] - 64 <= ey <= bbox[3] + 64,
                   f"game {viewer.name}: the partner is at the partner's real screen position",
                   expected=(ex, ey), bbox=bbox)
        # The tint multiplies the sprite by (0x60, 0x70, 0xA0)/0x80: blue gains 2x on red.
        run.expect(rgb[2] >= rgb[0] * 1.15, f"game {viewer.name}: the partner is tinted blue", mean_rgb=rgb)
    bot = walker("left", attack_every=8)  # walk_entrance_rooms' way out of Death's room
    room0 = a.snapshot()["room"]
    run.step(1500, p1=lambda i, sa, sb: (bot(sa or a.snapshot(), i), ""))
    run.expect(a.snapshot()["room"] != room0, "A walked into another room", room=a.snapshot()["room"])
    bbox, count, _ = partner_pixels(b)
    run.expect(bbox is None, "B draws no partner once A is in another room", pixels=count, bbox=bbox)


@session_scenario(starts=("no0", "no0"))
def map_marker(run):
    """Criterion 6: on B's map screen, a second cursor marks A's room."""
    a, b = run.s.a, run.s.b
    run.step(300)                          # stage title card
    run.step(240, p1=("right", ""))        # A walks off B's screen
    run.step(1, p1=("", "select"))         # B opens the map (in a shared room, that freezes A)
    run.step(40)
    run.expect(b.read("g_GameEngineStep") == 20, "B is on the map screen", step=b.read("g_GameEngineStep"))
    p = a.mailbox("self_presence")
    ex, ey = (p.room_left + (p.x >> 8)) * 4 - 14, (p.room_top + (p.y >> 8)) * 4 - 13
    bbox, count, _ = partner_pixels(b, frames=20)
    run.expect(bbox is not None, "B's map shows a partner cursor", pixels=count)
    run.expect(ex <= bbox[0] <= ex + 16 and ey <= bbox[1] <= ey + 16 and bbox[2] - bbox[0] <= 32,
               "the cursor is on A's map cell", cell=(p.room_left + (p.x >> 8), p.room_top + (p.y >> 8)),
               expected_corner=(ex, ey), bbox=bbox)


@session_scenario()
def stale_link(run):
    """Criterion 7: kill game B's process. A keeps running, and within a second it stops drawing B."""
    a, b = run.s.a, run.s.b
    run.step(60, p1=("right", ""))
    run.expect(partner_pixels(a)[0] is not None, "A draws B while B is alive")
    b.proc.kill()
    b.proc.join(5)
    for _ in range(60):
        s = a.step(1, "left")
    run.expect(s["game_state"] == 2 and s["hp"] > 0, "A keeps playing", state=s["game_state"])
    run.expect(a.mailbox("partner_age") > 30, "A's partner went stale", age=a.mailbox("partner_age"))
    run.expect(partner_pixels(a)[0] is None, "A no longer draws B")


EXCLUDED_FLAGS = (0x13, 0x14, 0x34)  # module/progress.c: not progress


def assert_converged(run):
    a, b = run.s.a, run.s.b
    fa, fb = bytearray(a.read_bytes("g_CastleFlags", 0x300)), bytearray(b.read_bytes("g_CastleFlags", 0x300))
    for i in EXCLUDED_FLAGS:
        fa[i] = fb[i] = 0
    diff = [hex(i) for i in range(0x300) if fa[i] != fb[i]]
    run.expect(not diff, "castle flags identical in both games", differ=diff[:10])
    run.expect(a.read_bytes("g_CastleMap", 0x800) == b.read_bytes("g_CastleMap", 0x800), "maps identical")
    ga, gb = a.read("g_Status", "<i", 0x28C), b.read("g_Status", "<i", 0x28C)
    run.expect(ga == gb, "pooled gold identical", a=ga, b=gb)


def heal(g):
    """Harness-only: HP to max, so ten minutes of button-mashing doesn't end in Game Over."""
    g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)


def soak(run, minutes):
    """M1 criterion 8, revised for M2: both games, random input, sharing a room some of the time,
    for `minutes`. No crash, no events lost, and the shared state converges: castle flags (but
    the excluded ones), map, and pooled gold are identical in both games at the end.
    (M1 also checked that the link never changes game state. Since M2 it does, on purpose.)"""
    a, b = run.s.a, run.s.b
    frames = int(minutes * 3600)
    inputs_a = list(random_inputs(11, frames))
    inputs_b = list(random_inputs(22, frames))
    shared = [0]

    def each(i, sa, sb):
        if sa["stage"] == sb["stage"] and sa["room"] == sb["room"]:
            shared[0] += 1
        if (i + 1) % 600 == 0:
            heal(a), heal(b)

    run.s.step(frames, p1=lambda i, sa, sb: (inputs_a[i][0], inputs_b[i][0]), each=each)
    run.s.step(30)  # let the last events land
    sa, sb = a.snapshot(), b.snapshot()
    run.expect(sa["game_state"] == 2 and a.mailbox("heartbeat") > frames, "A still in play", final=sa)
    run.expect(sb["game_state"] == 2, "B still in play", final=sb)
    run.expect(shared[0] > frames // 20, "the games shared a room part of the time", frames=shared[0])
    run.expect(a.mailbox("dropped") == 0 and b.mailbox("dropped") == 0, "no events dropped")
    assert_converged(run)




@session_scenario()
def soak_short(run):
    soak(run, 1)


@session_scenario()
def soak_10min(run):
    soak(run, 10)


@session_scenario()
def soak_30min(run):
    soak(run, 30)
