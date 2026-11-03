"""Online play as players meet it (playtest 2026-11-01): the game's own route, Alucard with
Richter, over a simulated connection like the playtest's (link/netsim.py "playtest"). The other
network tests stay in one room; these change rooms, load and teleport, and they measure what
the players felt: dropped game frames and bytes on the wire, room by room."""

import struct

from session import session_scenario

from coop_env import TOOLS
from module import symbols
from session_m8 import as_characters
from session_progress import arrive
from session_shared import into_hall

GAME_FRAMES = "g_Timer"  # one per frame the game finishes
PROFILE, SEED = "playtest", 1
ENV_POOL, ENV_SIZE = 0x800974AC, 0x40  # DRA's 16 DR_ENV entries


STARTS = TOOLS["out"].parent / "fixtures" / "debug-starts"
ENTITY_SIZE, PRIM_SIZE, PRIM_COUNT = 0xBC, 0x34, 0x500
FLAGS_OFS, ID_OFS, PRIM_INDEX_OFS, EXT_OFS = 0x34, 0x26, 0x64, 0x7C  # Entity
R1_OFS = 0x10  # Primitive
FLAG_HAS_PRIMS = 0x800000
AFTERIMAGE_PRIMS = 8  # Alucard's chain: its 9th is the DR_ENV's
GATE_ROOM = (2, 38)
DOOR_X = 105
RUN_THE_FOREST = 2400


class Meter:
    """Per room of each game: frames, the game's frames among them, and wire bytes sent."""

    def __init__(self, run):
        self.run, self.rooms, self.last = run, {}, None

    def tick(self):
        now = []
        for g in self.run.s.games:
            p = g.mailbox("self_presence")
            now.append((g.read("g_Timer"), g.transport("wan_stats")["bytes_sent"], p.stage, p.room))
        if self.last:
            for name, (t0, w0, *_), (t1, w1, stage, room) in zip("AB", self.last, now):
                r = self.rooms.setdefault((name, stage, room), {"frames": 0, "game": 0, "bytes": 0})
                r["frames"] += 1
                r["game"] += t1 - t0
                r["bytes"] += w1 - w0
        self.last = now

    def expect(self):
        rooms = {f"{n} stage {s:#x} room {r}": v for (n, s, r), v in sorted(self.rooms.items())}
        worst = min((v["game"] / v["frames"] for v in self.rooms.values() if v["frames"] >= 300), default=1)
        kbit = max((v["bytes"] * 8 * 60 / 1000 / v["frames"] for v in self.rooms.values() if v["frames"] >= 300), default=0)
        self.run.expect(worst >= 0.95, "the game keeps its frames in every room", worst=round(worst, 3), rooms=rooms)
        self.run.expect(kbit < 1500, "no room needs over 1.5 Mbit/s upload", kbit=round(kbit))


def afterimages(g):
    """Alucard's afterimage slot still owns its primitives."""
    return bool(g.read("g_Entities", "<I", ENTITY_SIZE + FLAGS_OFS) & FLAG_HAS_PRIMS)


def _forest(run, meter=None):
    """Both players run the forest and into the gate's room, and on."""
    rooms = [[], []]
    for t in range(RUN_THE_FOREST):
        run.step(1, ("right+cross" if t % 40 < 20 else "right",) * 2)
        if meter:
            meter.tick()
        for k, g in enumerate(run.s.games):
            room = g.snapshot()["room"]
            if not rooms[k] or rooms[k][-1] != room:
                rooms[k].append(room)
    return rooms


def _through_the_gate(run):
    run.s.set_net(PROFILE, SEED)
    meter = Meter(run)
    rooms = _forest(run, meter)
    x = [g.snapshot()["world_x"] for g in run.s.games]
    run.expect(all(GATE_ROOM in r for r in rooms), "both reach the gate", rooms=rooms)
    run.expect(all(r[-1] != GATE_ROOM or v >= DOOR_X for r, v in zip(rooms, x)),
               "neither is shut out at the castle door", rooms=rooms, x=x)
    meter.expect()


@session_scenario(starts=("no3_start", "no3_start"), characters=(0, 1))
def netplay_gate_alucard_and_richter(run):
    """Playtest 2026-11-01: the door shut behind the first in, with the other outside for good."""
    _through_the_gate(run)


@session_scenario(starts=("no3_start", "no3_start"), characters=(1, 0), full=True)
def netplay_gate_richter_and_alucard(run):
    _through_the_gate(run)


@session_scenario(starts=("no3_start", "no3_start"), characters=(0, 1))
def netplay_lost_afterimages_repaired(run):
    """The playtest's freeze: Alucard's afterimage primitives gone, his DR_ENV pointer read from
    a primitive that isn't his. The game's own write through it would reach the exception
    vector (CrashGuard); the module sets his afterimages up again first."""
    s, a = run.s, run.s.a
    sym = symbols()
    s.set_net(PROFILE, SEED)
    run.step(120)
    index = a.read("g_Entities", "<i", ENTITY_SIZE + PRIM_INDEX_OFS)
    prim = a.addr("g_PrimBuf") + index * PRIM_SIZE
    for _ in range(AFTERIMAGE_PRIMS):
        prim = a.read(prim)
    a.write(prim, 0x101, "<I", R1_OFS)  # as the playtest's: another entity's colours
    flags = a.read("g_Entities", "<I", ENTITY_SIZE + FLAGS_OFS)
    a.write("g_Entities", flags & ~FLAG_HAS_PRIMS, "<I", ENTITY_SIZE + FLAGS_OFS)
    run.step(30, ("right", "right"))
    run.expect(afterimages(a) and a.read(sym["g_CoopAfterimagesRepaired"]) == 1,
               "Alucard's afterimages are set up again", repaired=a.read(sym["g_CoopAfterimagesRepaired"]))


def _comings_and_goings(run, times=30):
    """B leaves A's room and comes back: its body is made and dropped in A's game each time."""
    s, a, b = run.s, run.s.a, run.s.b
    s.set_net(PROFILE, SEED)
    into_hall(run)
    p = a.mailbox("self_presence")
    for _ in range(times):
        arrive(run, b, 0x0C, 176, 104, 36)
        run.step(90)
        arrive(run, b, p.stage, p.room_id, p.ground_x + 24, p.ground_y)
        run.step(90)
    run.expect(afterimages(a) and afterimages(b), "both players keep their afterimages' primitives")
    run.expect(a.read(symbols()["g_CoopAfterimagesRepaired"]) == 0, "nothing needed repairing")


@session_scenario(characters=(0, 1), full=True)
def netplay_comings_and_goings_alucard_and_richter(run):
    _comings_and_goings(run)


@session_scenario(characters=(1, 0), full=True)
def netplay_comings_and_goings_richter_and_alucard(run):
    _comings_and_goings(run)


def _keeps_running(run, frames, bots):
    """Neither game's main loop may stop (a hang leaves the emulator running)."""
    s = run.s
    s.set_net(PROFILE, SEED)
    snaps = [g.snapshot() for g in s.games]
    timers = [g.read("g_Timer") for g in s.games]
    for t in range(frames):
        snaps = [g.step(1, bot(sn, t)) for g, bot, sn in zip(s.games, bots, snaps)]
        s.guard.check(s.games)
        if t % 120 == 119:
            now = [g.read("g_Timer") for g in s.games]
            run.expect(all(n > w for n, w in zip(now, timers)), "both games keep running", frame=t,
                       rooms=[x["room"] for x in snaps], timers=now)
            timers = now
        if t % 10 == 0:
            bad = [foreign_prims(g) for g in s.games]
            run.expect(not any(bad), "every entity keeps to its own primitives", frame=t, bad=bad)


def foreign_prims(g):
    """Stage entities whose own data points at primitives outside their own chain."""
    raw = g.read_bytes("g_Entities", ENTITY_SIZE * 256)
    buf = g.addr("g_PrimBuf")
    bad = {}
    for slot in range(64, 256):
        e = raw[slot * ENTITY_SIZE:(slot + 1) * ENTITY_SIZE]
        eid, flags = struct.unpack_from("<H", e, ID_OFS)[0], struct.unpack_from("<I", e, FLAGS_OFS)[0]
        if not eid or not flags & FLAG_HAS_PRIMS:
            continue
        chain, p = set(), buf + struct.unpack_from("<i", e, PRIM_INDEX_OFS)[0] * PRIM_SIZE
        while p and p not in chain and len(chain) < PRIM_COUNT:
            chain.add(p)
            p = g.read(p)
        words = struct.unpack_from("<16I", e, EXT_OFS)
        far = [hex(w) for w in words if buf <= w < buf + PRIM_COUNT * PRIM_SIZE and w not in chain]
        if far:
            bad[slot] = (eid, far)
    return bad


@session_scenario(starts=(str(STARTS / "Marble Gallery.state"),) * 2, characters=(0, 1))
def netplay_marble_gallery_axe_knight(run):
    """Found by harness/realtime.py: a guest's Axe Knight, its room handed over, walked the
    primitive chain of the authority's numbering for good, and Richter's game stopped."""
    from bots import walker
    as_characters(run, 0, 1)
    _keeps_running(run, 1500, [walker("right", 24), walker("left", 24)])


def partner_lag(run, frames=1200, profile=PROFILE):
    """How far behind each game shows the other player, in frames, sampled every frame while both
    walk the hall: the partner's own frame counter now, minus the one stamped on the presence this
    game is showing (CoopPresence.frame: the sender's g_Timer when it was captured). That's the
    whole way: the network, the jitter buffer (link/playout.py), and the frames in between."""
    from bots import walker
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.s.set_net(profile, SEED)
    run.step(300)  # the jitter buffer settles
    lags = ([], [])
    bots = (walker("right", attack_every=30), walker("left", attack_every=30))
    for t in range(frames):
        run.step(1, p1=tuple(bots[k](g.snapshot(), t) for k, g in enumerate((a, b))))
        for k, (me, them) in enumerate(((a, b), (b, a))):
            p = me.mailbox("partner_presence")
            if p.frame:
                lags[k].append(them.read(GAME_FRAMES) - p.frame)
    out = []
    for k, lag in enumerate(lags):
        lag.sort()
        out.append({"median_ms": round(lag[len(lag) // 2] * 1000 / 60), "p95_ms": round(lag[int(len(lag) * 0.95)] * 1000 / 60),
                    "max_ms": round(lag[-1] * 1000 / 60)})
    return out


@session_scenario(characters=(0, 1))
def netplay_partner_lag(run):
    """Issue: about half a second between a player's move and the partner seeing it (playtest
    0.14). On the playtest's connection (30 ms each way, jitter, hitches), each game shows the
    other at most one way's delay plus a few frames behind, most of the time."""
    lag = partner_lag(run)
    one_way = 30  # with the old jitter buffer: 133 ms (median); the network and a frame or two: 50 to 67
    for k, m in enumerate(lag):
        run.expect(m["median_ms"] <= one_way + 50, f"{'AB'[k]} sees {'BA'[k]} {m['median_ms']} ms behind (median)", **m)
