"""Three players (M17 step 4, design/M17-more-players.md): three linked games, each with a Host per
partner (session.Session with three starts). Each game runs a body for each of its two partners,
each from its own VRAM bank (partner k's is bank k + 1), and two partners on one character share
its partner build, each with its statics of its own (module/partner.c Statics). All in --full only
(the design's risks: every test doubles in cost)."""

from link.mailbox import CHAR_ALUCARD, CHAR_RICHTER
from link.mesh import slot
from module import symbols
from session import session_scenario  # first: puts `link` on the path

BODY_SIZE = 0x3C50  # one partner's copy in g_CoopSpikeBody (partner.c BODY_SIZE)
DRAW_OFS = 64 * 0xBC + 0x3D0 + 0x4A0  # g_PlayerDraw in the copy (partner.c DRAW_OFS)
POSE = 0x56  # Entity.animCurFrame


def body(game, k):
    """Partner k's body in that game: its copy of "the player" (entity 0 first)."""
    return symbols()["g_CoopSpikeBody"] + k * BODY_SIZE


def follow(run, pads, frames):
    """Plays pads (one per game) for that many frames, sampling every game's bodies against the
    partner's real spot. Returns {(game, partner): (worst px, samples, poses seen)}."""
    games = run.s.games
    seen = {(i, j): [0, 0, set()] for i in range(3) for j in range(3) if i != j}

    def each(t, *snaps):
        for (i, j), got in seen.items():
            g, k = games[i], slot(i, j)
            got[2].add(g.read(body(g, k), "<H", POSE))
            if t % 10 or snaps[i]["room"] != snaps[j]["room"]:
                continue
            bx = g.read(body(g, k), "<h", 2) + g.read("g_Tilemap", "<h", 0x0A)
            got[0] = max(got[0], abs(bx - snaps[j]["world_x"]))
            got[1] += 1
    run.step(frames, lambda t, *s: pads[t % len(pads)], each)
    return seen


def pattern(*moves):
    out = []
    for pad, n in moves:
        out += [pad] * n
    return out


def bodies(run, label):
    """B runs right and jumps, C runs left and jumps, A stands: in every game, both partners'
    bodies are made, follow their partners and animate, each from its own bank."""
    b = pattern(("right", 60), ("right+cross", 14), ("right", 40), ("left", 60), ("", 40))
    c = pattern(("left", 50), ("left+cross", 14), ("", 30), ("right", 50), ("right+cross", 14), ("", 56))
    run.step(30)
    seen = follow(run, [("", b[t], c[t]) for t in range(len(b))], 2 * len(b))
    for i, g in enumerate(run.s.games):
        made = g.read(symbols()["g_CoopBodiesMade"])
        run.expect(made & 3 == 3, f"{'ABC'[i]} runs both partners' bodies", made=made)
        for k in range(2):
            y = g.read(body(g, k), "<h", DRAW_OFS + 2)  # rect0.y: where its sprites upload
            run.expect(y >> 9 == k + 1, f"{'ABC'[i]}'s body for partner {k} draws from bank {k + 1}", y=hex(y))
    for (i, j), (worst, samples, poses) in seen.items():
        run.expect(samples > 10 and worst <= 48, f"{label}: {'ABC'[i]}'s body of {'ABC'[j]} follows it",
                   worst_px=worst, samples=samples)
    for i, j in ((0, 1), (0, 2)):
        run.expect(len(seen[i, j][2]) > 6, f"{label}: A's body of {'ABC'[j]} animates", poses=len(seen[i, j][2]))
    for g in run.s.games:
        run.expect(g.snapshot()["hp"] > 0, "every game plays on")


@session_scenario(starts=("entrance",) * 3, full=True)
def partner_bodies_three_players(run):
    """Three Alucards: each game draws both partners' bodies, from banks 1 and 2."""
    bodies(run, "three Alucards")


@session_scenario(starts=("entrance",) * 3, characters=(CHAR_ALUCARD, CHAR_RICHTER, CHAR_RICHTER), full=True)
def partner_bodies_two_richters(run):
    """B and C both Richter: A runs both bodies on the one Richter partner build, each with its own
    statics (partner.c Statics), so each moves and animates as its own player does."""
    from session_m8 import reload_game
    for g, c in zip(run.s.games, (CHAR_ALUCARD, CHAR_RICHTER, CHAR_RICHTER)):
        run.expect(reload_game(run, g) and g.mailbox("self_presence").character == c, f"{g.name} plays {c}")
    bodies(run, "Alucard and two Richters")
    a = run.s.a
    run.expect(a.read(body(a, 0), "<h", 0x54) == a.read(body(a, 1), "<h", 0x54) == run.s.b.read("g_Entities", "<h", 0x54),
               "A's two bodies are Richter's")


@session_scenario(starts=("entrance",) * 3, full=True)
def rules_enemy_hp_three_players(run):
    """#316: three players hear from each other: enemies have 2.75x the castle's HP for one, and
    2x once one of them goes silent for 10 s."""
    from module import stage_symbol
    from session_m11 import ENEMY_DEF_SIZE
    from session_rules import DEF_HP
    defs = stage_symbol("dra", "g_EnemyDefs")
    slogra, base = 243, 200
    a = run.s.a

    def hp():
        return a.read(defs, "<h", slogra * ENEMY_DEF_SIZE + DEF_HP)
    for g in run.s.games:
        g._ask("call", ("hosts", "set_rules", ((0, 0, 0, 0, 0),), {}))
    run.step(30)
    run.expect(hp() == base * 275 // 100, "three players: 2.75x", hp=hp())
    run.s.c.partition(True)
    run.step(11 * 60)
    run.expect(hp() == base * 2, "C silent for 10 s: 2x", hp=hp())


# --- step 5: shared rooms, progression and joining, for every partner ----------------------------

@session_scenario(starts=("entrance",) * 3, full=True)
def shared_rooms_three_players(run):
    """Criterion 1: A walks into the entrance hall first (the authority); B and C arrive beside it.
    Both are guests, each with exactly A's stage entities and their HP."""
    from bots import walker
    from link.mailbox import ROLE_AUTHORITY, ROLE_GUEST
    from session_progress import arrive
    from session_shared import HALL, stage_entities
    a, b, c = run.s.games
    bot = walker("left", attack_every=0)
    for i in range(1500):
        run.step(1, lambda t, *s: (bot(a.snapshot(), i), "", ""))
        if a.snapshot()["room"] == HALL and i > 200:
            break
    run.step(120)
    p = a.mailbox("self_presence")
    for g, dx in ((b, 24), (c, 48)):
        arrive(run, g, p.stage, p.room_id, p.ground_x + dx, p.ground_y)
    run.step(60)
    roles = [g.mailbox("self_presence").role for g in run.s.games]
    run.expect(roles == [ROLE_AUTHORITY, ROLE_GUEST, ROLE_GUEST], "A runs the hall, B and C are its guests", roles=roles)
    ea = stage_entities(a)
    enemies = {s for s, e in ea.items() if e[3] > 0}
    run.expect(enemies, "the hall has enemies", entities=len(ea))
    for g in (b, c):
        eg = stage_entities(g)
        run.expect(set(eg) == set(ea), f"{g.name} has exactly A's stage entities",
                   only_a=sorted(set(ea) - set(eg))[:8], only_them=sorted(set(eg) - set(ea))[:8])
        run.expect(all(eg[s][3] == ea[s][3] for s in enemies if s in eg), f"{g.name}'s enemies have A's HP")


@session_scenario(starts=("entrance",) * 3, full=True)
def gold_pooled_three_players(run):
    """Criterion 1: one purse for three. C's gold change reaches A and B, once each; then B's
    spending reaches A and C."""
    from session_progress import GOLD, STATUS, status
    games = run.s.games
    run.step(5)
    g0 = status(run.s.a)["gold"]
    run.s.c.write(STATUS, g0 + 400, "<i", GOLD)
    run.step(10)
    golds = [status(g)["gold"] for g in games]
    run.expect(golds == [g0 + 400] * 3, "C +400: all three at +400", golds=golds)
    run.s.b.write(STATUS, golds[1] - 150, "<i", GOLD)
    run.step(10)
    golds = [status(g)["gold"] for g in games]
    run.expect(golds == [g0 + 250] * 3, "B -150: all three at +250", golds=golds)


CASTLE_FLAG = 0x2F0  # a castle flag nothing in the entrance uses


@session_scenario(starts=("entrance",) * 3, full=True)
def castle_flags_rejoin_three_players(run):
    """Criterion 3: C is away (its links cut) while A finds something (a castle flag); B gets it at
    once, and C when it comes back, with nothing lost or doubled; enemy HP follows the players."""
    a, b, c = run.s.games
    run.step(30)
    c.partition(True)
    run.step(11 * 60)
    a.write("g_CastleFlags", 1, "<B", CASTLE_FLAG)
    run.step(30)
    run.expect(b.read("g_CastleFlags", "<B", CASTLE_FLAG) == 1, "B has A's find at once")
    run.expect(c.read("g_CastleFlags", "<B", CASTLE_FLAG) == 0, "C, away, doesn't yet")
    c.partition(False)
    run.step(120)
    flags = [g.read("g_CastleFlags", "<B", CASTLE_FLAG) for g in run.s.games]
    run.expect(flags == [1, 1, 1], "C back: it has A's find too", flags=flags)
    all_flags = [g.read_bytes("g_CastleFlags", 0x300) for g in run.s.games]
    run.expect(all_flags[0] == all_flags[1] == all_flags[2], "every castle flag is the same in all three")


def _slogra():
    """The debug start in front of Slogra and Gaibon."""
    from coop_env import TOOLS
    return str(TOOLS["out"].parent / "fixtures" / "debug-starts" / "Boss - Slogra and Gaibon.state")


@session_scenario(starts=(_slogra(),) * 3, full=True)
def boss_aggro_three_players(run):
    """Criterion 1: Slogra and Gaibon with three players in the arena. Their HP is 2.75x the
    castle's for one, and in the game running the room they go for every player in turn: itself
    and both partners (module/boss.c g_CoopAggroSeen)."""
    from bots import walker
    from link.mailbox import CONTROL_AGGRO_SHIFT, ROLE_AUTHORITY
    from module import stage_symbol
    from session_m11 import ENEMY_DEF_SIZE
    from session_rules import DEF_HP
    games = run.s.games
    for g in games:
        g.mailbox("set_control", 0xFF << CONTROL_AGGRO_SHIFT)  # a switch at nearly every chance
    run.step(60)
    defs = stage_symbol("dra", "g_EnemyDefs")
    run.expect(run.s.a.read(defs, "<h", 243 * ENEMY_DEF_SIZE + DEF_HP) == 200 * 275 // 100, "Slogra at 2.75x")
    bots = [walker("left", attack_every=20) for _ in games]  # through the door (launcher/bossstarts.py: walk left)
    seen = 0
    for i in range(3600):
        run.step(1, lambda t, *s: tuple(bot(g.snapshot(), i) for bot, g in zip(bots, games)))
        if i % 60 == 0:
            for g in games:
                if g.mailbox("self_presence").role == ROLE_AUTHORITY:
                    seen = g.read(symbols()["g_CoopAggroSeen"])
            if seen & 7 == 7:
                break
    run.expect(seen & 7 == 7, "the bosses went for each of the three", seen=bin(seen), frames=i)


@session_scenario(starts=("nz0",) * 4, full=True)
def online_4p_lossy(run):
    """M17 criterion 6: four games, every link on the playtest's network (30 ms, jitter, loss,
    spikes), walking about the Alchemy Lab for 30 s while each now and then finds some gold. Gold
    is one purse: all four end with the same, and every game still hears all three partners."""
    from link.mailbox import IN_PLAY
    games = run.s.games
    for i, g in enumerate(games):
        for k in range(3):
            g._ask("call", (f"transport{k}", "set_netsim", ("playtest", 7 * i + k), {}))
        g._ask("call", ("hosts", "set_playout", (True,), {}))
    run.step(60)
    gold = lambda g: g.read("g_Status", "<i", 0x28C)
    start = gold(games[0])
    pads = ("left", "right", "", "left")
    for t in range(1800):
        flip = (t // 90) % 2
        run.step(1, tuple(p if flip else ("right" if p == "left" else "left") for p in pads))
        if t % 300 == 100:
            g = games[(t // 300) % 4]
            g.write("g_Status", gold(g) + 100, "<i", 0x28C)
    run.step(300, ("",) * 4)  # settle
    purses = [gold(g) for g in games]
    run.expect(len(set(purses)) == 1 and purses[0] == start + 600, "one purse: every find counted once, in all four",
               purses=purses, start=start)
    ages = [[g.mailbox("partner_age", k) for k in range(3)] for g in games]
    run.expect(all(a < 30 for row in ages for a in row), "every game hears all three partners", ages=ages)
    run.expect(all(g.mailbox("self_presence").flags & IN_PLAY for g in games), "all four still in play")
