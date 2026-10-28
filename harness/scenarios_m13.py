"""M13 spike (design/M13-partner-player.md): the partner simulated by the game's own player code,
in one game, driven by scripted buttons (module/partner.c, OPT_PARTNER_SIM). Measures what the
spike must answer: the partner moves as its buttons say, player 1 is untouched, the frame cost,
and determinism."""

import struct

from link.mailbox import OPT_PARTNER_SIM
from module import COOP_DISC, symbols
from scenario import scenario
from scenarios_m8 import mailbox

PAD = {"": 0, "right": 0x2000, "left": 0x8000, "cross": 0x40}  # PAD_* (include/game.h)
SCANLINES = 263  # NTSC: a frame


def body_x(e):
    """The partner's entity 0 (the first thing in its copy): world x."""
    raw = e.read_bytes(symbols()["g_CoopSpikeBody"], 0xBC)
    return struct.unpack_from("<h", raw, 2)[0]


def run_partner(run, partner, p1, sim=True):
    """Both players' buttons, frame by frame: (partner pad names, player 1 pad names)."""
    e, mb = run.emu, mailbox(run)
    mb.set_options(OPT_PARTNER_SIM if sim else 0)
    for pp, b in zip(partner, p1):
        e.write(symbols()["g_CoopSpikePad"], sum(PAD[k] for k in pp.split("+") if k))
        run.step(1, b)


@scenario(start="entrance", disc=COOP_DISC)
def m13_spike_partner_sim(run):
    """The spike's four measurements, except the VRAM patch (drawing)."""
    e = run.emu
    start = e.save_state()
    script = ["right"] * 120 + [""] * 30 + ["cross"] * 16 + [""] * 60 + ["left"] * 90
    p1 = ["left"] * 30 + ["right"] * 30 + [""] * 256  # moves, but stays in the room (the copy is camera-relative)
    # 1. it moves as its buttons say
    run_partner(run, script[:2], p1[:2])
    x0 = body_x(e)
    run_partner(run, script[2:120], p1[2:120])
    x1 = body_x(e)
    run_partner(run, script[120:], p1[120:])
    x2 = body_x(e)
    run.expect(x1 > x0 + 40 and x2 < x1, "the partner walks right, then left, on its own buttons", x=(x0, x1, x2))
    with_sim = e.snapshot()
    ram_a = e.read_bytes(0x80000000, 0x200000)
    run.step(1)
    shot_on = e.screenshot()
    cost = e.read(symbols()["g_CoopSpikeMax"])
    last = e.read(symbols()["g_CoopSpikeLines"])
    # 2. player 1 is untouched: the same run without the partner
    e.load_state(start)
    run_partner(run, script, p1, sim=False)
    alone = e.snapshot()
    run.step(1)
    shot_off = e.screenshot()
    from PIL import ImageChops
    from coop_env import TOOLS
    out = TOOLS["out"] / run.name
    out.mkdir(parents=True, exist_ok=True)
    shot_on.save(out / "partner_on.png")
    shot_off.save(out / "partner_off.png")
    box = ImageChops.difference(shot_on.convert("RGB"), shot_off.convert("RGB")).getbbox()
    run.expect(box is not None, "the partner is drawn (the screen differs only by it)", box=box)
    same = {k: (with_sim[k], alone[k]) for k in ("world_x", "world_y", "hp", "room") if with_sim[k] != alone[k]}
    run.expect(not same, "player 1 ends the same with or without the partner", differ=same)
    # 4. determinism: the same inputs, the same RAM
    e.load_state(start)
    run_partner(run, script, p1)
    ram_b = e.read_bytes(0x80000000, 0x200000)
    differ = [i for i in range(0, 0x200000, 4) if ram_a[i:i + 4] != ram_b[i:i + 4]]
    run.expect(not differ, "the same inputs give the same 2 MB of RAM", words=len(differ), first=[hex(0x80000000 + i) for i in differ[:5]])
    # 3. the frame cost (last: the other checks still run)
    run.expect(cost < SCANLINES // 4, "the partner's frame costs under a quarter of a frame",
               scanlines=cost, percent=round(100 * cost / SCANLINES, 1), last=last)


# --- the partner's body in a two-game session ------------------------------------------------
from session import session_scenario  # noqa: E402


@session_scenario(starts=("entrance", "entrance"))
def m13_partner_body_follows(run):
    """Game A simulates B's body from B's buttons (played out with B's presence) while B walks
    and jumps around the room: A's copy stays with B's real spot (within the snap distance), and
    A's own player is untouched; no puppet is drawn while the body is."""
    from link.mailbox import OPT_PARTNER_SIM
    a, b = run.s.a, run.s.b
    a.host("set_player", options=OPT_PARTNER_SIM)
    body = symbols()["g_CoopSpikeBody"]
    run.step(30)
    worst, samples = 0, 0
    pattern = ["right"] * 60 + ["right+cross"] * 14 + ["right"] * 40 + ["left"] * 80 + ["left+cross"] * 14 + [""] * 40
    for t, pad in enumerate(pattern * 2):
        run.step(1, ("", pad))
        if t % 10 == 0:
            raw = a.read_bytes(body, 0xBC)
            bx = struct.unpack_from("<h", raw, 2)[0] + a.read("g_Tilemap", "<h", 0x0A)  # + scrollX.i.hi
            sb = b.snapshot()
            if sb["room"] == a.snapshot()["room"]:
                worst = max(worst, abs(bx - sb["world_x"]))
                samples += 1
    run.expect(samples > 20 and worst <= 48, "A's copy of B stays with B (within the snap distance)",
               worst_px=worst, samples=samples)
    run.expect(a.snapshot()["hp"] > 0, "A plays on")


@session_scenario(starts=("entrance", "entrance"))
def m13_partner_status(run):
    """The partner's body fights as the partner: B's status (stats, level, equipment) reaches A
    and is in A's copy of B, while A's own status is untouched."""
    from link.mailbox import OPT_PARTNER_SIM, STATUS_RANGES
    a, b = run.s.a, run.s.b
    a.host("set_player", options=OPT_PARTNER_SIM)
    run.step(30)
    mine = b"".join(a.read_bytes(addr, n) for addr, n in STATUS_RANGES)
    b.write(0x80097BE8, 42)                    # g_Status.level
    b.write(0x80097BB8, 77)                    # statsBase[STR]
    b.write(0x80097C00, 0x0D)                  # equipment[0], the right hand
    run.step(60)
    theirs = b"".join(b.read_bytes(addr, n) for addr, n in STATUS_RANGES)
    # where g_Status's two ranges are in the copy (partner.c's s_Regions, in order)
    body = symbols()["g_CoopSpikeBody"]
    ofs = 64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4) + 0x280 + 8 + 4
    copy = a.read_bytes(body, 0x48, ofs) + a.read_bytes(body, 0x34, ofs + 0x48)
    run.expect(copy == theirs, "A's copy of B has B's status",
               differ=[i for i in range(len(theirs)) if copy[i] != theirs[i]][:8])
    now = b"".join(a.read_bytes(addr, n) for addr, n in STATUS_RANGES)
    same = [i for i in range(len(mine)) if now[i] != mine[i] and not 0 <= i < 0x18]  # hp..mpMax may tick
    run.expect(not same, "A's own status is its own", differ=same[:8])
