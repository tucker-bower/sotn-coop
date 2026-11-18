"""A castle's rules (D162, design/M-castle-rules.md): each rule in two real games. The defaults are
the rest of the suite, which runs with no rules set; these turn a rule off, or move its slider, and
check the game follows. The launcher's side: launcher/test_rules.py, uxdriver's rules flow."""

from link.mailbox import RULE_NO_SHARED_GOLD
from session import session_scenario  # first: puts `link` on the path

LIFE_APPLE = 0x26 + 0x92  # g_Status.equipHandCount[ITEM_LIFE_APPLE], from g_Status

DEF_HP = 4              # EnemyDef.hitPoints
LEAP_STONE = 13         # g_Status.relics
ACTIVE = 3              # found, switched on


def rules(run, off=0, exp=0, dealt=0, taken=0, enemy_hp=0):
    """The castle's rules in both games, as the launcher sets them."""
    for g in (run.s.a, run.s.b):
        g.host("set_rules", (off, exp, dealt, taken, enemy_hp))
    run.step(3)


@session_scenario()
def rules_reach_the_game(run):
    """The host writes them every frame, so a savestate's old ones can't stay."""
    a = run.s.a
    rules(run, RULE_NO_SHARED_GOLD, exp=150, enemy_hp=300)
    run.expect(a.mailbox("rules") == (RULE_NO_SHARED_GOLD, 150, 0, 0, 300), "in the mailbox", got=a.mailbox("rules"))
    a.mailbox("set_rules")
    run.step(2)
    run.expect(a.mailbox("rules")[0] == RULE_NO_SHARED_GOLD, "written back the next frame", got=a.mailbox("rules"))




@session_scenario()
def rules_enemy_hp_follows_players(run):
    """#316: the castle's enemy HP is for one player, and the game multiplies it by the players it
    hears from (module/boss.c PLAYERS_HP): Slogra at Hard (150%) has 2 x 150% of its HP while the
    partner is there, 150% once the partner has been silent for 10 s, and 2 x 150% again when the
    partner comes back."""
    from module import stage_symbol
    from session_m11 import ENEMY_DEF_SIZE
    a = run.s.a
    defs = stage_symbol("dra", "g_EnemyDefs")
    slogra, base = 243, 200  # boss.c's list; enemydefs.yaml

    def hp():
        return a.read(defs, "<h", slogra * ENEMY_DEF_SIZE + DEF_HP)
    rules(run, enemy_hp=150)
    run.step(30)
    run.expect(hp() == base * 2 * 150 // 100, "two players at Hard: 2 x 150%", hp=hp())
    for g in (run.s.a, run.s.b):
        g.partition(True)
    run.step(11 * 60)
    run.expect(hp() == base * 150 // 100, "the partner silent for 10 s: one player's 150%", hp=hp())
    for g in (run.s.a, run.s.b):
        g.partition(False)
    run.step(120)
    run.expect(hp() == base * 2 * 150 // 100, "the partner back: 2 x 150% again", hp=hp())
