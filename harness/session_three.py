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

