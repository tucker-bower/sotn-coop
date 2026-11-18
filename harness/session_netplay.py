"""Online play as players meet it (playtest 2026-11-01): the game's own route, Alucard with
Richter, over a simulated connection like the playtest's (link/netsim.py "playtest"). The other
network tests stay in one room; these change rooms, load and teleport, and they measure what
the players felt: dropped game frames and bytes on the wire, room by room."""


from session import session_scenario

from coop_env import TOOLS
from module import symbols
from session_shared import into_hall

PROFILE, SEED = "playtest", 1
ENV_POOL, ENV_SIZE = 0x800974AC, 0x40  # DRA's 16 DR_ENV entries


STARTS = TOOLS["out"].parent / "fixtures" / "debug-starts"
ENTITY_SIZE, PRIM_SIZE, PRIM_COUNT = 0xBC, 0x34, 0x500
FLAGS_OFS, ID_OFS, PRIM_INDEX_OFS, EXT_OFS = 0x34, 0x26, 0x64, 0x7C  # Entity
FLAG_HAS_PRIMS = 0x800000


def afterimages(g):
    """Alucard's afterimage slot still owns its primitives."""
    return bool(g.read("g_Entities", "<I", ENTITY_SIZE + FLAGS_OFS) & FLAG_HAS_PRIMS)


def _body_track(run, frames, pads):
    """B's body as A's game draws it, in world x, each frame, while pads(t) drive both."""
    a, body = run.s.a, symbols()["g_CoopSpikeBody"]
    xs = []
    for t in range(frames):
        run.step(1, p1=pads(t))
        if a.mailbox("partner_presence").flags:
            xs.append(a.read(body, "<h", 2) + a.read("g_Tilemap", "<h", 0xA))
    return xs


@session_scenario(characters=(0, 1))
def netplay_partner_runs_smoothly_alucard_and_richter(run):
    """#291 (1.1.1 playtest): online, Alucard saw Richter "jumping all over" as he ran. On the
    playtest's connection, Richter runs one way and back across the hall, where the zombies knock
    him back in his game but not his body in A's. On A's screen his body is eased back to his real
    spot: no step over 16 px (it was put there in one step once 48 px off: three 47-52 px jumps
    in this run). A drift that easing can't close is put right after a second, a step of about 12-16 px."""
    into_hall(run)
    run.s.set_net(PROFILE, SEED)
    run.step(300)
    xs = _body_track(run, 480, lambda t: ("", "right" if t < 240 else "left"))
    steps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    leaps = [(i, s) for i, s in enumerate(steps) if abs(s) > 16]
    run.expect(len(xs) > 400, "A shows B's body", samples=len(xs))
    run.expect(not leaps, "B's body never jumps more than 16 px in a frame", leaps=leaps[:12], n=len(leaps))
