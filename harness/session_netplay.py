"""Online play as players meet it (playtest 2026-11-01): the game's own route, Alucard with
Richter, over a simulated connection like the playtest's (link/netsim.py "playtest"). The other
network tests stay in one room; these change rooms, load and teleport, and they measure what
the players felt: dropped game frames and bytes on the wire, room by room."""

import struct

from session import session_scenario

from module import symbols
from session_progress import arrive
from session_shared import into_hall

GAME_FRAMES = "g_Timer"  # one per frame the game finishes
PROFILE, SEED = "playtest", 1
ENV_POOL, ENV_SIZE = 0x800974AC, 0x40  # DRA's 16 DR_ENV entries


ENTITY_SIZE, PRIM_SIZE = 0xBC, 0x34
FLAGS_OFS, ID_OFS, PRIM_INDEX_OFS = 0x34, 0x26, 0x64  # Entity
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
