"""Online play as players meet it (playtest 2026-11-01): the game's own route, Alucard with
Richter, over a simulated connection like the playtest's (link/netsim.py "playtest"). The other
network tests stay in one room; these change rooms, load and teleport, and they measure what
the players felt: dropped game frames and bytes on the wire, room by room."""


from session import session_scenario

from coop_env import TOOLS
from module import symbols
from session_scenarios import heal
from session_shared import into_hall

PROFILE, SEED = "playtest", 1
ENV_POOL, ENV_SIZE = 0x800974AC, 0x40  # DRA's 16 DR_ENV entries


STARTS = TOOLS["out"].parent / "fixtures" / "debug-starts"
ENTITY_SIZE, PRIM_SIZE, PRIM_COUNT = 0xBC, 0x34, 0x500
FLAGS_OFS, ID_OFS, PRIM_INDEX_OFS, EXT_OFS = 0x34, 0x26, 0x64, 0x7C  # Entity
FLAG_HAS_PRIMS = 0x800000
HP_ADDR = 0x80097BA0  # g_Status.hp (link/mailbox.py STATUS_HP)


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


def _world(g, base, ofs=0):
    """An entity's spot in its game's room: its screen x, y plus that game's camera."""
    return (g.read(base, "<h", ofs + 2) + g.read("g_Tilemap", "<h", 0xA),
            g.read(base, "<h", ofs + 6) + g.read("g_Tilemap", "<h", 0xE))


def _runner(seed):
    """B's buttons: runs, turns and jumps of 8-40 frames, the same each time for a seed, each
    followed by its mirror so B stays about where it started (in the room)."""
    import random
    rng, out = random.Random(seed), []
    flip = {"right": "left", "left": "right", "": "", "right+cross": "left+cross", "left+cross": "right+cross"}
    while len(out) < 4000:
        move, n = rng.choice(("right", "left", "", "right+cross", "left+cross")), rng.randint(8, 40)
        out += [move] * n + [flip[move]] * n
    return out


def _lag(body, real):
    """How many frames behind B's own game A shows B's body: the delay that best lines the two up
    (median distance), and that distance."""
    best = None
    for d in range(0, 25):
        errs = sorted(abs(body[t][0] - real[t - d][0]) + abs(body[t][1] - real[t - d][1])
                      for t in range(d, len(body)) if body[t] and real[t - d])
        med = errs[len(errs) // 2]
        if best is None or med < best[1]:
            best = (d, med)
    return best


@session_scenario(characters=(0, 1))
def netplay_partner_on_time_alucard_and_richter(run):
    """#86 rollback (design/rollback.md option A): on the playtest's connection, A's game shows
    Richter's body where Richter is in his own game now, not half a round trip and the jitter
    buffer ago. A rewinds and runs again where a guess at his buttons was wrong. Measured against
    the same run with rollback off; on a LAN, nothing runs ahead. A misses no more frames for it."""
    a, b = run.s.a, run.s.b
    body, sym = symbols()["g_CoopSpikeBody"], symbols()
    from session_m8 import reload_game
    run.expect(reload_game(run, b) and b.mailbox("self_presence").character == 1, "B plays Richter")
    into_hall(run)
    run.step(120)
    pads = _runner(7)

    hits = {"b": 0, "body": 0}

    def phase(frames, start, hurt=False):
        real, shown, drawn = [], [], []
        t0 = a.read("g_Timer")
        hp, body_hits = b.read(HP_ADDR, "<i"), a.read(sym["g_CoopBodyHits"])
        for t in range(frames):
            if hurt and t % 150 == 75 and b.read(HP_ADDR, "<i") > 20:  # a hit in his own game (HP down)
                b.write(HP_ADDR, b.read(HP_ADDR, "<i") - 5, "<i")
            run.step(1, p1=("", pads[start + t]))
            now = b.read(HP_ADDR, "<i")
            hits["b"] += 0 < now < hp
            hp = now
            together = a.snapshot()["room"] == b.snapshot()["room"]
            real.append(_world(b, "g_Entities") if together else None)
            shown.append(_world(a, body) if together else None)
            drawn.append((shown[-1][0] + a.read(sym["g_CoopRollDrawn"], "<h"),
                          shown[-1][1] + a.read(sym["g_CoopRollDrawn"], "<h", 2)) if together else None)
        hits["body"] = a.read(sym["g_CoopBodyHits"]) - body_hits
        return real, shown, drawn, frames - (a.read("g_Timer") - t0)

    _, _, _, missed_lan = phase(600, 0)
    run.expect(a.read(sym["g_CoopRollFrames"]) == 0, "on a LAN the body runs on the presence, nothing ahead",
               ran=a.read(sym["g_CoopRollFrames"]))
    run.s.set_net(PROFILE, SEED)
    for g in (a, b):
        g.host("set_rollback", False)
    run.step(300)
    real0, shown0, _, _ = phase(900, 600)
    lag0 = _lag(shown0, real0)
    for g in (a, b):
        g.host("set_rollback", True)
        g.host("set_suggestions", False)
    run.step(120)
    real2, shown2, _, _ = phase(600, 2400)
    lag2 = _lag(shown2, real2)  # rollback without the partner's suggestions
    for g in (a, b):
        g.host("set_suggestions", True)
    run.step(120)
    rew0 = a.read(sym["g_CoopRollRewinds"])
    hits["b"] = 0
    heal(b)
    real1, shown1, drawn1, missed = phase(900, 1500, hurt=True)
    lag1 = _lag(shown1, real1)
    rewinds = a.read(sym["g_CoopRollRewinds"]) - rew0
    steps = [abs(drawn1[i + 1][0] - drawn1[i][0]) for i in range(len(drawn1) - 1) if drawn1[i] and drawn1[i + 1]]
    run.expect(len(steps) > 600, "B stays in A's room", frames=len(steps))
    run.expect(rewinds > 0, "A ran Richter again from a wrong guess", rewinds=rewinds,
               aborts=a.read(sym["g_CoopRollAborts"]), behind=a.read(sym["g_CoopRollBehind"]))
    run.expect(lag1[0] <= 1 and lag1[0] < lag0[0], "Richter's body is shown on time (at most a frame behind)",
               rollback=lag1, without_suggestions=lag2, without=lag0)
    run.expect(hits["b"] >= 5 and hits["body"] == hits["b"], "each hit Richter takes in his game lands on his body here, once",
               his_game=hits["b"], body=hits["body"])
    run.expect(max(steps) <= 16, "a wrong guess slides the body back: no step over 16 px",
               biggest=max(steps), over_16=sum(s > 16 for s in steps))
    run.expect(missed <= missed_lan * 1.5 + 3, "A misses no more frames for it", missed=missed, lan=missed_lan,
               rollback_lines_max=a.read(sym["g_CoopRollLinesMax"]), behind=a.read(sym["g_CoopRollBehind"]))


STAGE_START, STAGE_SLOTS = 64, 192
CAMERA_LOCKED = 0x08000000


def _copies(g):
    """A game's stage entities that move with the room: slot -> (id, room x, room y)."""
    raw = g.read_bytes("g_Entities", STAGE_SLOTS * ENTITY_SIZE, STAGE_START * ENTITY_SIZE)
    sx, sy = g.read("g_Tilemap", "<h", 0xA), g.read("g_Tilemap", "<h", 0xE)
    out = {}
    for i in range(STAGE_SLOTS):
        e = raw[i * ENTITY_SIZE:(i + 1) * ENTITY_SIZE]
        eid = int.from_bytes(e[ID_OFS:ID_OFS + 2], "little")
        flags = int.from_bytes(e[FLAGS_OFS:FLAGS_OFS + 4], "little")
        if eid and flags & CAMERA_LOCKED and not int.from_bytes(e[0x68:0x6A], "little"):
            out[i] = (eid, int.from_bytes(e[2:4], "little", signed=True) + sx,
                      int.from_bytes(e[6:8], "little", signed=True) + sy)
    return out


def _drift(run, frames, pads):
    """Each frame, how far B's copies are from A's enemies now (px, x + y), of those moving in A's
    game, and how far each copy moved on B's screen since the last frame (but for 8 frames after
    A's own enemy jumped)."""
    a, b = run.s.a, run.s.b
    errs, steps, last, seen, leapt = [], [], {}, {}, {}
    for t in range(frames):
        run.step(1, p1=pads(t))
        ca, cb = _copies(a), _copies(b)
        for i, (eid, x, y) in ca.items():  # moving in A's game: where it was 4 frames ago
            seen.setdefault(i, []).append((eid, x, y))
            del seen[i][:-5]
            if len(seen[i]) > 1 and abs(x - seen[i][-2][1]) + abs(y - seen[i][-2][2]) > 16:
                leapt[i] = t  # a real jump in A's game: B's copy makes it too, a little later
        for i, (eid, x, y) in cb.items():
            if i in ca and ca[i][0] == eid and len(seen[i]) == 5 and seen[i][0] != ca[i]:
                errs.append(abs(x - ca[i][1]) + abs(y - ca[i][2]))
            if i in last and last[i][0] == eid and t - leapt.get(i, -99) > 8:
                steps.append(abs(x - last[i][1]) + abs(y - last[i][2]))
        last = cb
    errs.sort()
    return errs, steps


@session_scenario()
def netplay_room_enemies_steady_on_lag(run):
    """#292 (design/rollback.md option B): online, a guest's copies of the shared room's enemies
    drifted from where they were and jumped. On the playtest's connection, B's copies are moved on
    by their own motion for the snapshot's age and through gaps, and eased into each new snapshot:
    nearer A's enemies than without it (median), and no copy jumps more than 16 px in a frame."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.s.set_net(PROFILE, SEED)
    walk = lambda t: ("right" if (t // 90) % 2 else "left", "")
    for g in (a, b):
        g.host("set_extrapolate", False)
    run.step(300)
    errs0, steps0 = _drift(run, 600, walk)
    for g in (a, b):
        g.host("set_extrapolate", True)
    run.step(120)
    errs1, steps1 = _drift(run, 600, lambda t: walk(t + 600))
    med0, med1 = errs0[len(errs0) // 2], errs1[len(errs1) // 2]
    run.expect(len(errs1) > 300, "B mirrors A's moving enemies", samples=len(errs1))
    run.expect(med1 <= 8 and med1 < med0, "B's copies are within 8 px of A's enemies (median), nearer than without",
               median=med1, without=med0, p90=errs1[len(errs1) * 9 // 10], p90_without=errs0[len(errs0) * 9 // 10])
    run.expect(sum(s > 16 for s in steps1) == 0, "no copy jumps more than 16 px in a frame",
               jumps=sum(s > 16 for s in steps1), jumps_without=sum(s > 16 for s in steps0),
               eased=a.read(symbols()["g_CoopCopiesEased"]) + b.read(symbols()["g_CoopCopiesEased"]))
