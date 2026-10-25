"""M11 acceptance tests: castles, solo, one shared level (design/M11-castles.md).

Kills are real: A walks into the castle entrance hall (NO3 room 14,40) and fights its zombies,
so the stage's own hit code grants the XP through g_api.func_800FE044 (our GrantWrap). B stays
in the room it started in, so the kill is A's alone. A zombie's XP (5) is raised to 40 in both
games' enemy table first, so that half of it is told apart from all of it."""

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from module import stage_symbol
from session_progress import EXP, LEVEL, STATUS, status
from session_shared import HALL, stage_entities

ENEMY_DEF_SIZE, DEF_LEVEL, DEF_EXP = 0x28, 0x16, 0x18  # EnemyDef (include/game.h)
ENTITY_SIZE, ENEMY_ID = 0xBC, 0x3A
ZOMBIE_EXP = 40


def kill_xp(amount, player_level, enemy_level):
    """What func_800FE044 adds for a kill (DRA 5D5BC.c): scaled by the level gap."""
    x = amount
    for _ in range(max(0, player_level - enemy_level)):
        x = x * 2 // 3
    x = max(1, x) if player_level > enemy_level else x
    for _ in range(min(5, max(0, enemy_level - player_level))):
        x += x // 4
    return x


def walk_into_hall(run):
    a = run.s.a
    bot = walker("left", attack_every=0)
    for i in range(1500):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if a.snapshot()["room"] == HALL and i > 200:
            break
    run.step(60)


def enemy_ids(g):
    """The enemyIds of the stage entities alive in g's room."""
    raw = g.read_bytes("g_Entities", ENTITY_SIZE * 256)
    return {int.from_bytes(raw[s * ENTITY_SIZE + ENEMY_ID:s * ENTITY_SIZE + ENEMY_ID + 2], "little")
            for s, e in stage_entities(g).items() if e[3] > 0}


def fight_until_xp(run, frames=1200):
    """A attacks its way left until its XP goes up. Returns A's XP before and after."""
    a = run.s.a
    before = status(a)["exp"]
    bot = walker("left", attack_every=6)
    for i in range(frames):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if status(a)["exp"] != before:
            return before, status(a)["exp"]
    return before, before


@session_scenario()
def m11_shared_xp(run):
    """M11 criterion 2: A's kill gives A half the XP (a partner is linked), and B gains exactly
    what A gained. Then, from just short of the next level, A's kill levels up both games."""
    a, b = run.s.a, run.s.b
    walk_into_hall(run)
    run.expect(a.snapshot()["room"] != b.snapshot()["room"], "A and B are in different rooms",
               a=a.snapshot()["room"], b=b.snapshot()["room"])
    defs = stage_symbol("dra", "g_EnemyDefs")
    ids = enemy_ids(a)
    run.expect(ids, "the hall has enemies")
    for g in (a, b):
        for eid in ids:
            g.write(defs, ZOMBIE_EXP, "<H", eid * ENEMY_DEF_SIZE + DEF_EXP)
    enemy_level = max(a.read(defs, "<H", eid * ENEMY_DEF_SIZE + DEF_LEVEL) for eid in ids)
    level = status(a)["level"]
    b0 = status(b)["exp"]
    x0, x1 = fight_until_xp(run)
    gained = x1 - x0
    run.expect(gained > 0, "A killed an enemy and gained XP", gained=gained)
    want = kill_xp(ZOMBIE_EXP // 2, level, enemy_level)
    run.expect(gained == want, "A gained half the kill's XP",
               gained=gained, half=want, full=kill_xp(ZOMBIE_EXP, level, enemy_level))
    run.step(30)
    run.expect(status(b)["exp"] - b0 == gained, "B gained exactly what A gained",
               b_gained=status(b)["exp"] - b0, a_gained=gained)

    # Level up together: both just short of the next level, then one kill by A
    exp_next = stage_symbol("dra", "g_ExpNext")
    lv = status(a)["level"]
    run.expect(status(b)["level"] == lv, "the same level before", a=lv, b=status(b)["level"])
    short = a.read(exp_next, "<i", (lv + 1) * 4) - 1
    for g in (a, b):
        g.write(STATUS, short, "<i", EXP)
    run.step(5)
    x0, x1 = fight_until_xp(run, frames=1800)
    run.expect(x1 > x0, "A killed another enemy", exp=x1)
    run.step(60)
    la, lb = status(a)["level"], status(b)["level"]
    run.expect(la == lb == lv + 1, "both games levelled up", before=lv, a=la, b=lb)
    run.expect(status(a)["exp"] == status(b)["exp"], "with the same XP",
               a=status(a)["exp"], b=status(b)["exp"])
