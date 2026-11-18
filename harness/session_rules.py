"""A castle's rules (D162, design/M-castle-rules.md): each rule in two real games. The defaults are
the rest of the suite, which runs with no rules set; these turn a rule off, or move its slider, and
check the game follows. The launcher's side: launcher/test_rules.py, uxdriver's rules flow."""

from link.mailbox import RULE_NO_SHARED_GOLD
from session import session_scenario  # first: puts `link` on the path

LIFE_APPLE = 0x26 + 0x92  # g_Status.equipHandCount[ITEM_LIFE_APPLE], from g_Status

DEF_HP = 4              # EnemyDef.hitPoints
LEAP_STONE = 13         # g_Status.relics
ACTIVE = 3              # found, switched on


def rules(run, off=0, exp=0, dealt=0, taken=0, enemy_hp=0, enemy_hp_solo=0):
    """The castle's rules in both games, as the launcher sets them."""
    for g in (run.s.a, run.s.b):
        g.host("set_rules", (off, exp, dealt, taken, enemy_hp, enemy_hp_solo))
    run.step(3)


@session_scenario()
def rules_reach_the_game(run):
    """The host writes them every frame, so a savestate's old ones can't stay."""
    a = run.s.a
    rules(run, RULE_NO_SHARED_GOLD, exp=150, enemy_hp=300)
    run.expect(a.mailbox("rules") == (RULE_NO_SHARED_GOLD, 150, 0, 0, 300, 0), "in the mailbox", got=a.mailbox("rules"))
    a.mailbox("set_rules")
    run.step(2)
    run.expect(a.mailbox("rules")[0] == RULE_NO_SHARED_GOLD, "written back the next frame", got=a.mailbox("rules"))


