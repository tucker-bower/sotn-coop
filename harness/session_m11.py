"""M11 acceptance tests: castles, solo, one shared level (design/M11-castles.md).

Kills are real: A walks into the castle entrance hall (NO3 room 14,40) and fights its zombies,
so the stage's own hit code grants the XP through g_api.func_800FE044 (our GrantWrap). B stays
in the room it started in, so the kill is A's alone. A zombie's XP (5) is raised to 40 in both
games' enemy table first, so that half of it is told apart from all of it."""

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from module import stage_symbol
from session_progress import EXP, STATUS, status
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


def shared_xp(run):
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


# --- castles: real games, each "PC" its own data folder (launcher/test_castles.py: the rules)

import sys as _sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

_sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))

from link.jointsave import read_session, save_room  # noqa: E402
from link.mailbox import BUSY, CARD_OK, IN_PLAY  # noqa: E402
from module import COOP_DISC  # noqa: E402
from session import OnlineSession  # noqa: E402
from session_online import COFFIN, NZ0, SAVE_ROOM, step_pair  # noqa: E402

SLOGRA, SLOGRA_HP, DEF_HP = 243, 200, 0x04  # boss.c's list; enemydefs.yaml


def data(name):
    """A PC's Documents\\SOTN Co-op (test_castles.pc() switches to it)."""
    return Path(tempfile.mkdtemp(prefix=f"coop-m11-{name}-"))


def online(start, rank, castle=None):
    return OnlineSession(COOP_DISC, start=start, rank=rank, bind_host="127.0.0.1", joint=True,
                         session_file=castle.joint_save if castle else None)


def link(s0, s1):
    s0.connect(("127.0.0.1", s1.port))
    s1.connect(("127.0.0.1", s0.port))


def until(s0, s1, cond, frames):
    for i in range(frames):
        step_pair(s0, s1, 1)
        if cond():
            return True
    return False


@session_scenario()
def castle_solo_play(run):
    """M11 criterion 1: a solo game (no partner) has 1x boss HP and full kill XP, and its save
    writes slot 1 of its castle."""
    from archive import Castle
    from test_castles import pc
    defs = stage_symbol("dra", "g_EnemyDefs")
    run.step(30)  # the couch pair, linked: Slogra has twice its HP there
    run.expect(run.s.a.read(defs, "<h", SLOGRA * ENEMY_DEF_SIZE + DEF_HP) == 2 * SLOGRA_HP,
               "linked (couch): Slogra has 2x HP", hp=run.s.a.read(defs, "<h", SLOGRA * ENEMY_DEF_SIZE + DEF_HP))
    me = data("solo")
    with pc(me):
        castle = Castle.new()
    with online("entrance", 0, castle) as s:
        s.step(30)
        g = s.local
        run.expect(g.read(defs, "<h", SLOGRA * ENEMY_DEF_SIZE + DEF_HP) == SLOGRA_HP, "solo: Slogra has 1x HP",
                   hp=g.read(defs, "<h", SLOGRA * ENEMY_DEF_SIZE + DEF_HP))
        bot = walker("left", attack_every=0)
        for i in range(1500):
            s.step(1, bot(g.snapshot(), i))
            if g.snapshot()["room"] == HALL and i > 200:
                break
        s.step(60)
        ids = enemy_ids(g)
        for eid in ids:
            g.write(defs, ZOMBIE_EXP, "<H", eid * ENEMY_DEF_SIZE + DEF_EXP)
        enemy_level = max(g.read(defs, "<H", eid * ENEMY_DEF_SIZE + DEF_LEVEL) for eid in ids)
        level, x0 = status(g)["level"], status(g)["exp"]
        bot = walker("left", attack_every=6)
        for i in range(1200):
            s.step(1, bot(g.snapshot(), i))
            if status(g)["exp"] != x0:
                break
        gained = status(g)["exp"] - x0
        run.expect(gained == kill_xp(ZOMBIE_EXP, level, enemy_level), "solo: a kill gives its full XP",
                   gained=gained, full=kill_xp(ZOMBIE_EXP, level, enemy_level))
        g.mailbox("command", 1, NZ0, SAVE_ROOM, *COFFIN)
        for _ in range(300):
            s.step(1)
            p = g.mailbox("self_presence")
            if p.stage == NZ0 and p.room_id == SAVE_ROOM and p.flags & IN_PLAY and not p.flags & BUSY:
                break
        s.step(60)
        s.step(2, "up")
        for _ in range(900):
            s.step(1)
            if castle.joint_save.exists():
                break
        run.expect(castle.joint_save.exists() and len(read_session(castle.joint_save)) == 1,
                   "solo: the coffin saves slot 1 of the castle, with no partner to wait for")


