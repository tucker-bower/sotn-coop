"""A castle's rules (D162, design/M-castle-rules.md): each rule in two real games. The defaults are
the rest of the suite, which runs with no rules set; these turn a rule off, or move its slider, and
check the game follows. The launcher's side: launcher/test_rules.py, uxdriver's rules flow."""

from link.mailbox import (BUSY, CHAR_RICHTER, CHAR_ULT_MARIA, CUTSCENE, DEAD, IN_PLAY, OPT_NO_AIR_JUMPS, OPT_NO_ALUCARD_STATS,
                          OPT_NO_GROWTH,
                          OPT_NO_RELIC_MOVES, OPT_PARTNER_SIM, RULE_NO_BOSS_PULL, RULE_NO_FAERIE_REVIVE,
                          RULE_NO_MAP_TELEPORT, RULE_NO_OFFHAND, RULE_NO_REVIVE, RULE_NO_SCENE_PULL,
                          RULE_NO_SHARED_GOLD, RULE_NO_SHARED_LEVEL)
from session import session_scenario  # first: puts `link` on the path
from module import stage_symbol
from session_m5 import LEFT_OF_MARIA, NO0, into_boss_room, wait_pulled
from session_m8 import reload_game
from scenarios_m8 import HALL_ROOM, NO3
from session_m11 import (DEF_EXP, DEF_LEVEL, ENEMY_DEF_SIZE, ZOMBIE_EXP, enemy_ids, fight_until_xp, kill_xp,
                         walk_into_hall)
from session_m15 import load_characters
from session_progress import EXP, GOLD, RELICS, STATUS, arrive, status
from session_shared import into_hall
from session_travel import die, map_teleport

LIFE_APPLE = 0x26 + 0x92  # g_Status.equipHandCount[ITEM_LIFE_APPLE], from g_Status

DEF_HP = 4              # EnemyDef.hitPoints
DOPPLEGANGER = 253      # the first-castle boss the no1 start meets
LEAP_STONE = 13         # g_Status.relics
ACTIVE = 3              # found, switched on


def rules(run, off=0, exp=0, dealt=0, taken=0, enemy_hp=0, enemy_hp_solo=0):
    """The castle's rules in both games, as the launcher sets them."""
    for g in (run.s.a, run.s.b):
        g.host("set_rules", (off, exp, dealt, taken, enemy_hp, enemy_hp_solo))
    run.step(3)


def hall_kill(run):
    """A walks into the hall (B stays out) and kills a zombie of known XP: (A's gain, the gain the
    game gives `amount` XP, B's gain)."""
    a, b = run.s.a, run.s.b
    walk_into_hall(run)
    defs = stage_symbol("dra", "g_EnemyDefs")
    ids = enemy_ids(a)
    run.expect(ids, "the hall has enemies")
    for g in (a, b):
        for eid in ids:
            g.write(defs, ZOMBIE_EXP, "<H", eid * ENEMY_DEF_SIZE + DEF_EXP)
    enemy = max(a.read(defs, "<H", eid * ENEMY_DEF_SIZE + DEF_LEVEL) for eid in ids)
    level, b0 = status(a)["level"], status(b)["exp"]
    x0, x1 = fight_until_xp(run)
    run.step(10)
    return x1 - x0, lambda amount: kill_xp(amount, level, enemy), status(b)["exp"] - b0


@session_scenario()
def rules_reach_the_game(run):
    """The host writes them every frame, so a savestate's old ones can't stay."""
    a = run.s.a
    rules(run, RULE_NO_SHARED_GOLD, exp=150, enemy_hp=300)
    run.expect(a.mailbox("rules") == (RULE_NO_SHARED_GOLD, 150, 0, 0, 300, 0), "in the mailbox", got=a.mailbox("rules"))
    a.mailbox("set_rules")
    run.step(2)
    run.expect(a.mailbox("rules")[0] == RULE_NO_SHARED_GOLD, "written back the next frame", got=a.mailbox("rules"))


@session_scenario()
def rules_host_tells_joiner(run):
    """The host's rules are in every HELO, and a change gets there within a second."""
    a, b = run.s.a, run.s.b
    for pct in (200, 300):
        a.host("set_rules", (0, pct, 0, 0, 0, 0), {"exp_pct": pct})
        run.step(90)
        heard = (b.host("status").get("partner_hello") or {}).get("rules")
        run.expect(heard == {"exp_pct": pct}, f"the joiner hears {pct}%", heard=heard)


@session_scenario()
def rules_xp_percent(run):
    """XP gain 200%: a kill gives twice the XP, then it's split; B gets what A got."""
    rules(run, exp=200)
    gained, xp, b = hall_kill(run)
    run.expect(gained == xp(ZOMBIE_EXP), "A gains 200% of the half", gained=gained, want=xp(ZOMBIE_EXP))
    run.expect(b == gained, "B gains the same", b=b)


@session_scenario()
def rules_xp_own_level(run):
    """One shared level off: A's kill gives A all of it, and B nothing."""
    rules(run, RULE_NO_SHARED_LEVEL)
    gained, xp, b = hall_kill(run)
    run.expect(gained == xp(ZOMBIE_EXP), "A gains all of it", gained=gained, want=xp(ZOMBIE_EXP))
    run.expect(b == 0, "B gains nothing", b=b)


@session_scenario()
def rules_gold_apart(run):
    """One purse off: A's gold stays A's."""
    a, b = run.s.a, run.s.b
    rules(run, RULE_NO_SHARED_GOLD)
    g0 = status(b)["gold"]
    a.write(STATUS, status(a)["gold"] + 400, "<i", GOLD)
    run.step(10)
    run.expect(status(b)["gold"] == g0, "B's gold doesn't change", b=status(b)["gold"], was=g0)


def scripted_hit(run, g, taken, attack=40, off=0):
    """g's HP lost to one hit, through its player's own damage code, at that rule."""
    rules(run, off, taken=taken)
    g.write(STATUS, status(g)["hp_max"], "<i", 0x23C)
    run.step(120)
    hp0 = status(g)["hp"]
    g.write("g_Entities", attack, "<h", 0x3E)  # PLAYER.hitPoints, as hit detection leaves them
    g.write("g_Entities", 1, "<H", 0x44)       # PLAYER.hitParams: a plain hit
    run.step(4)
    return hp0 - status(g)["hp"]


@session_scenario(starts=("entrance", "entrance"))
def rules_damage_taken(run):
    """Damage taken scales what Alucard loses, after his defense."""
    b = run.s.b
    base = scripted_hit(run, b, 0)
    run.expect(base > 0, "a hit hurts", lost=base)
    double, half = scripted_hit(run, b, 200), scripted_hit(run, b, 50)
    run.expect(abs(double - base * 2) <= 1, "200%: twice that", base=base, double=double)
    run.expect(abs(half - base // 2) <= 1, "50%: half", base=base, half=half)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, CHAR_RICHTER))
def rules_damage_taken_richter(run):
    """...and Richter, whose defense the module takes off first (issue 160)."""
    load_characters(run)
    b = run.s.b
    base = scripted_hit(run, b, 0)
    run.expect(base > 0, "a hit hurts", lost=base)
    double = scripted_hit(run, b, 200)
    run.expect(double == base * 2, "200%: twice that", base=base, double=double)


DEF_BUFF = 0x80139828  # g_StatBuffTimers[SBT_DEF]: 20 more defense while it runs (DRA's CalcDefense)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, CHAR_RICHTER))
def rules_richter_defense(run):
    """Issue 160: with "Alucard's stats" on, Richter's defense works as Alucard's does. 20 more defense (the
    DEF buff, as from gear) takes 20 off a hit. Off, his own code's rule: all of it."""
    load_characters(run)
    b = run.s.b
    base = scripted_hit(run, b, 0)
    run.expect(base > 0, "a hit hurts", lost=base)
    b.write(DEF_BUFF, 0x200, "<i")
    buffed = scripted_hit(run, b, 0)
    run.expect(buffed == max(1, base - 20), "20 more defense: 20 less lost", base=base, buffed=buffed)
    b.write(DEF_BUFF, 0x200, "<i")
    raw = scripted_hit(run, b, 0, off=OPT_NO_ALUCARD_STATS)
    run.expect(raw == 40, "off: the whole hit, as in his own game", lost=raw)


def plays_as_their_mod(run):
    """With every co-op character rule on (the default), Alucard's defense doesn't cut this
    character's hits, and EXP doesn't level them up (docs/design/character-mods.md)."""
    load_characters(run)
    b = run.s.b
    base = scripted_hit(run, b, 0)
    run.expect(base > 0, "a hit hurts", lost=base)
    b.write(DEF_BUFF, 0x200, "<i")
    buffed = scripted_hit(run, b, 0)
    run.expect(buffed == base, "20 more defense changes nothing for her", base=base, buffed=buffed)
    level = status(b)["level"]
    b.write(STATUS, 5000, "<I", EXP)
    run.step(60)
    run.expect(status(b)["level"] == level, "EXP doesn't level her up", level=(level, status(b)["level"]))


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_ULT_MARIA, CHAR_ULT_MARIA))
def rules_ultimate_maria_plays_as_ultimate(run):
    """Ultimate Maria plays as SOTN Ultimate built her, whatever the castle's rules."""
    plays_as_their_mod(run)


@session_scenario(starts=("entrance", "entrance"), characters=(5, 5))
def rules_ultimate_richter_plays_as_ultimate(run):
    """Ultimate Richter plays as retail Richter (SOTN Ultimate's), whatever the castle's rules."""
    plays_as_their_mod(run)


@session_scenario(starts=("entrance", "entrance"), characters=(4, 4))
def rules_saturn_maria_plays_as_ultimate(run):
    """Saturn Maria plays as SOTN Ultimate built her, whatever the castle's rules."""
    plays_as_their_mod(run)


@session_scenario()
def rules_damage_dealt(run):
    """Damage dealt 300%: a hit takes three times what it took."""
    from session_shared import stage_entities
    a = run.s.a
    walk_into_hall(run)

    def one_hit():
        from bots import walker
        bot = walker("left", attack_every=6)
        for s, e in stage_entities(a).items():
            a.write(a.entity(s), 5000, "<h", 0x3E)
        for i in range(900):
            run.step(1, p1=(bot(a.snapshot(), i), ""))
            lost = [5000 - e[3] for e in stage_entities(a).values() if 0 < e[3] < 5000]
            if lost:
                return lost[0]
        return None
    base = one_hit()
    run.expect(base, "A hit an enemy", lost=base)
    run.step(40)
    rules(run, dealt=300)
    triple = one_hit()
    run.expect(triple == base * 3, "300%: three times that", base=base, triple=triple)


@session_scenario(starts=("no1", "entrance"))
def rules_enemy_hp(run):
    """All enemies' HP follows both sliders: with a partner, then alone."""
    a = run.s.a
    defs = stage_symbol("dra", "g_EnemyDefs")
    hp = lambda: a.read(defs, "<h", DOPPLEGANGER * ENEMY_DEF_SIZE + DEF_HP)
    run.step(30)
    double = hp()
    rules(run, enemy_hp=300)
    run.expect(hp() == double // 2 * 3, "300% with a partner", hp=hp(), default=double)
    rules(run, enemy_hp=300, enemy_hp_solo=150)
    a.unlink()
    run.step(640)
    run.expect(hp() == double // 2 * 3 // 2, "150% alone", hp=hp(), default=double)


@session_scenario(starts=("entrance", "nz0"))
def rules_no_revive(run):
    """Revive off: a fallen player stays down, and not at a Game Over, while the partner lives."""
    a = run.s.a
    rules(run, RULE_NO_REVIVE)
    room = a.mailbox("self_presence").stage
    run.expect(die(run, a) is not None, "A died")
    run.step(1200)
    p = a.mailbox("self_presence")
    run.expect(p.flags & DEAD and p.stage == room, "A is still down", flags=p.flags, stage=p.stage)


@session_scenario(starts=("entrance", "entrance"))
def rules_no_faerie_revive(run):
    """Faerie revive off: the Life Apple stays, and A is revived the usual way."""
    a, b = run.s.a, run.s.b
    b.write(0x80097964 + 0x14, 3, "<B")  # the faerie card, on
    run.expect(reload_game(run, b), "B reloads with the faerie card on")
    for g in (a, b):
        g.write("g_Status", 1, "<B", LIFE_APPLE)
        g.host("set_player", options=OPT_PARTNER_SIM)
    rules(run, RULE_NO_FAERIE_REVIVE)
    into_hall(run)
    run.step(60)
    run.expect(die(run, a) is not None, "A died")
    run.step(600)
    run.expect(a.read("g_Status", "<B", LIFE_APPLE) == 1, "the apple is still there", apples=a.read("g_Status", "<B", LIFE_APPLE))
    run.expect(status(a)["hp"] > 0, "A came back all the same", hp=status(a)["hp"])


@session_scenario(starts=("no1", "entrance"))
def rules_no_boss_pull(run):
    """Bosses bring your partner off: B stays where it is."""
    a, b = run.s.a, run.s.b
    rules(run, RULE_NO_BOSS_PULL)
    run.expect(into_boss_room(run, a) is not None, "A is in a boss fight")
    run.expect(wait_pulled(run, b, a, 400) is None, "B wasn't pulled", b=str(b.mailbox("self_presence").room))


@session_scenario(starts=("no0", "entrance"))
def rules_no_scene_pull(run):
    """Scenes bring your partner off: A's scene starts without waiting, B stays where it is."""
    from bots import walker
    a, b = run.s.a, run.s.b
    rules(run, RULE_NO_SCENE_PULL)
    arrive(run, a, NO0, *LEFT_OF_MARIA)
    bot = walker("right", attack_every=0)
    for i in range(1800):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if a.mailbox("self_presence").flags & CUTSCENE:
            break
    run.expect(a.mailbox("self_presence").flags & CUTSCENE, "A's scene started")
    run.expect(wait_pulled(run, b, a, 300) is None, "B wasn't pulled", b=str(b.mailbox("self_presence").room))


@session_scenario(starts=("entrance", "nz0"))
def rules_no_map_teleport(run):
    """Teleport from the map off: Cross on the map stays where it is."""
    a, b = run.s.a, run.s.b
    rules(run, RULE_NO_MAP_TELEPORT)
    room = b.mailbox("self_presence").room
    map_teleport(run, b)
    run.step(240)
    run.expect(b.mailbox("self_presence").room == room, "B hasn't moved", room=str(b.mailbox("self_presence").room))


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, 0))
def rules_no_growth(run):
    """Richter and Maria level up off: XP doesn't level Richter up; back on, it does."""
    a = run.s.a
    load_characters(run)
    rules(run, OPT_NO_GROWTH)
    level = status(a)["level"]
    a.write(STATUS, status(a)["exp"] + 100000, "<i", EXP)
    run.step(30)
    run.expect(status(a)["level"] == level, "no level up", level=status(a)["level"], was=level)
    rules(run)
    run.step(30)
    run.expect(status(a)["level"] > level, "back on, he levels up", level=status(a)["level"], was=level)


def highest_jump(run, g):
    """How high g gets with a jump, and a second one at its top. Pixels above the ground."""
    y0 = g.snapshot()["world_y"]
    top = y0
    for pad in ["cross"] * 16 + [""] * 2 + ["cross"] * 2 + [""] * 60:
        run.step(1, p1=(pad, ""))
        top = min(top, g.snapshot()["world_y"])
    run.step(60)
    return y0 - top


def jump_rule(bit):
    def test(run):
        a = run.s.a
        load_characters(run)
        a.write(STATUS, ACTIVE, "<B", RELICS + LEAP_STONE)
        arrive(run, a, NO3, HALL_ROOM, 1300, 200)  # room to jump: the zombie hall
        run.step(90)
        with_jumps = highest_jump(run, a)
        rules(run, bit)
        without = highest_jump(run, a)
        run.expect(without < with_jumps, "lower without them", on=with_jumps, off=without)
    return test


def _register(name, doc, bit):
    fn = jump_rule(bit)
    fn.__name__, fn.__doc__ = name, doc
    session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, 0))(fn)


_register("rules_no_air_jumps", "Extra jumps off: the Leap Stone gives Richter no jump in the air.", OPT_NO_AIR_JUMPS)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, 0))
def rules_relic_moves_off_teaches_every_move(run):
    """#168: with "Relics teach Richter and Maria" off they know every move from the start.
    Richter without the Leap Stone has no jump in the air; with the rule off, he has it."""
    a = run.s.a
    load_characters(run)
    a.write(STATUS, 0, "<B", RELICS + LEAP_STONE)
    arrive(run, a, NO3, HALL_ROOM, 1300, 200)  # room to jump: the zombie hall
    run.step(90)
    without_relic = highest_jump(run, a)
    rules(run, OPT_NO_RELIC_MOVES)
    every_move = highest_jump(run, a)
    run.expect(every_move > without_relic, "higher: the Leap Stone's jump with no Leap Stone",
               relic_rule_on=without_relic, off=every_move)
    rules(run, OPT_NO_RELIC_MOVES | OPT_NO_AIR_JUMPS)
    run.expect(highest_jump(run, a) == without_relic, "extra jumps off still takes them away")


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, 0))
def rules_no_offhand(run):
    """Off-hand weapons off: Circle swings nothing; back on, it does."""
    from scenarios_m8 import EQUIPMENT, OFFHAND_ITEMS, offhand_entity
    a = run.s.a
    a.write(EQUIPMENT, OFFHAND_ITEMS[0][0])
    load_characters(run)
    run.step(90)  # the module loads the weapon

    def swings():
        for i in range(60):
            run.step(1, p1=("circle" if i % 24 == 0 else "", ""))
            if offhand_entity(a):
                return True
        return False
    rules(run, RULE_NO_OFFHAND)
    run.expect(not swings(), "no swing")
    rules(run)
    run.expect(swings(), "back on, it swings")
