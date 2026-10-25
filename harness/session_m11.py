"""M11 acceptance tests: castles, solo, one shared level (design/M11-castles.md).

Kills are real: A walks into the castle entrance hall (NO3 room 14,40) and fights its zombies,
so the stage's own hit code grants the XP through g_api.func_800FE044 (our GrantWrap). B stays
in the room it started in, so the kill is A's alone. A zombie's XP (5) is raised to 40 in both
games' enemy table first, so that half of it is told apart from all of it."""

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from link.mailbox import CHAR_ALUCARD, CHAR_RICHTER
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
    shared_xp(run)


@session_scenario(characters=(CHAR_ALUCARD, CHAR_RICHTER))
def m11_shared_xp_richter(run):
    """M11 risk: a Richter partner levels up from Alucard's kills too (character.c's Growth:
    only Alucard's own code checks EXP)."""
    from session_m8 import reload_game
    run.expect(reload_game(run, run.s.b), "B loads as Richter")
    run.expect(run.s.b.mailbox("self_presence").character == CHAR_RICHTER, "B plays Richter",
               b=run.s.b.mailbox("self_presence").character)
    shared_xp(run)


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


def coffin_save(s0, s1, saver, path_ok):
    """The saver walks into the Alchemy Lab's coffin and saves; returns when path_ok()."""
    saver.local.mailbox("command", 1, NZ0, SAVE_ROOM, *COFFIN)

    def there():
        p = saver.local.mailbox("self_presence")
        return p.stage == NZ0 and p.room_id == SAVE_ROOM and p.flags & IN_PLAY and not p.flags & BUSY
    until(s0, s1, there, 300)
    step_pair(s0, s1, 60)
    if saver is s0:
        step_pair(s0, s1, 2, p0="up")
    else:
        step_pair(s0, s1, 2, p1="up")
    return until(s0, s1, path_ok, 900)


def joiner_copy(run, s0, s1, pc_folder):
    """What the launcher does when the lobby connects (app.join_online): the copy of the
    host's castle, from its HELO."""
    from archive import Castle
    from test_castles import pc
    run.expect(until(s0, s1, lambda: (s1.local.host("status").get("partner_hello") or {}).get("castle"), 240),
               "the host's HELO names its castle")
    meta = s1.local.host("status")["partner_hello"]["castle"]
    with pc(pc_folder):
        copy = Castle.receive(meta)
    s1.joint.path = copy.joint_save
    s1.joint.on_write = lambda blobs: copy.saved(blobs, theirs=True)
    return copy


@session_scenario()
def m11_solo(run):
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


@session_scenario()
def m11_copy(run):
    """M11 criteria 3 and 4: A hosts castle X and B joins; their joint save leaves B with a copy
    of X (A's id and name, B in slot 1). Then B hosts its copy and C joins: B loads its own
    slot, C gets slot 2 (the last partner's), and C has a copy too. A's X is untouched."""
    from archive import Castle
    from test_castles import pc
    pa, pb, pcc = data("A"), data("B"), data("C")
    with pc(pa):
        x = Castle.new()
    with online("nz0", 0, x) as s0, online("entrance", 1) as s1:
        s0.joint.on_write = x.saved
        s0.local.host("set_castle", x.meta())
        link(s0, s1)
        copy = joiner_copy(run, s0, s1, pb)
        ok = coffin_save(s0, s1, s0, lambda: x.joint_save.exists() and copy.joint_save.exists())
        run.expect(ok, "the joint save reached both PCs")
    xa, xb = read_session(x.joint_save), read_session(copy.joint_save)
    run.expect(xb == xa[::-1], "B's copy: the same two saves, B in slot 1")
    with pc(pb):
        copy = Castle(copy.dir)
    run.expect(copy.info["id"] == x.info["id"] and copy.info["received"], "B's copy has X's id")
    with pc(pa):
        x = Castle(x.dir)
    run.expect(x.info.get("name") and copy.name == x.name, "and X's name", a=x.name, b=copy.name)
    a_file = x.joint_save.read_bytes()

    # B hosts its copy; C joins
    with pc(pb):
        copy.played_here()
    with online("entrance", 0, copy) as s0, online("entrance", 1) as s2:
        s0.local.host("set_castle", copy.meta())
        link(s0, s2)
        c_copy = joiner_copy(run, s0, s2, pcc)
        step_pair(s0, s2, 30)
        s0.joint.resume()
        run.expect(until(s0, s2, lambda: c_copy.joint_save.exists(), 300), "B continues its copy: C receives it")
        step_pair(s0, s2, 600)
        pb_now, pc_now = s0.local.mailbox("self_presence"), s2.local.mailbox("self_presence")
    xc = read_session(c_copy.joint_save)
    run.expect(xc[0] == xb[1] and xc[1] == xb[0], "C plays slot 2 (A's state, the last partner), B its own slot 1")
    run.expect(pb_now.stage == pc_now.stage == NZ0, "both play on from the save room", b=pb_now.stage, c=pc_now.stage)
    run.expect(c_copy.info["id"] == x.info["id"], "C's copy has X's id too")
    run.expect(x.joint_save.read_bytes() == a_file, "A's X is untouched")


@session_scenario()
def m11_slot2_clone(run):
    """M11 criterion 6: a castle only ever played solo (one slot) takes a partner: slot 2 starts
    as a copy of slot 1, in the same save room, at the same level."""
    from archive import Castle
    from link.jointsave import save_fields
    from test_castles import pc
    pa, pb = data("A"), data("B")
    with pc(pa):
        y = Castle.new()
    # A solo save: the host's own game saves in the coffin with no partner linked
    with online("nz0", 0, y) as s0, online("entrance", 1) as s1:
        ok = coffin_save(s0, s1, s0, lambda: y.joint_save.exists())
    run.expect(ok and len(read_session(y.joint_save)) == 1, "a solo save: one slot")
    solo = read_session(y.joint_save)[0]
    with online("entrance", 0, y) as s0, online("entrance", 1) as s1:
        s0.local.host("set_castle", y.meta())
        link(s0, s1)
        copy = joiner_copy(run, s0, s1, pb)
        step_pair(s0, s1, 30)
        s0.joint.resume()
        run.expect(until(s0, s1, lambda: copy.joint_save.exists(), 300), "the partner received the castle")
        step_pair(s0, s1, 600)
        p0, p1 = s0.local.mailbox("self_presence"), s1.local.mailbox("self_presence")
    got = read_session(copy.joint_save)
    run.expect(got[0] == solo and save_room(got[0]) == save_room(solo), "slot 2 is a copy of slot 1, in its save room")
    run.expect(save_fields(got[0])[2] == save_fields(solo)[2], "at the same level")
    run.expect(p0.stage == p1.stage == NZ0 and p0.room_id == p1.room_id, "both start in the save room",
               a=(p0.stage, p0.room_id), b=(p1.stage, p1.room_id))
