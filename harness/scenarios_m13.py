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
    p1 = ["left"] * 120 + [""] * 196
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
