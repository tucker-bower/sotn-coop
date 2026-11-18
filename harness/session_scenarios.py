"""M1 acceptance tests that need two linked games (design/M1-link-presence.md)."""


from PIL import ImageChops

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from coop_env import DISKS
from link.mailbox import PARTNER_AGE
from lockstep import random_inputs
from module import COOP_DISC, symbols

RETAIL = DISKS / "sotn.us.cue"


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
def stale_link(run):
    """Criterion 7: kill game B's process. A keeps running, and its copy of B outlasts a stall of
    the link, standing still, then goes (partner.c's BODY_STALE_FRAMES)."""
    a, b = run.s.a, run.s.b
    run.step(60, p1=("right", ""))
    run.expect(partner_pixels(a)[0] is not None, "A draws B while B is alive")
    b.proc.kill()
    b.proc.join(5)
    for _ in range(60):
        s = a.step(1, "left")
    run.expect(s["game_state"] == 2 and s["hp"] > 0, "A keeps playing", state=s["game_state"])
    run.expect(a.mailbox("partner_age") > 30, "A's partner went stale", age=a.mailbox("partner_age"))
    for _ in range(300):
        a.step(1)
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


