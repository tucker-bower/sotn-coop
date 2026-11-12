"""Widescreen in co-op (design/M19-widescreen.md, D201): each player sees their own screen shape,
and a shared room's enemies are kept alive for the wider of the two views."""

from session import session_scenario  # first: puts `link` on the path

from link.mailbox import OPT_WIDE_SHIFT, ROLE_AUTHORITY, ROLE_GUEST, WIDE_LINES, WIDE_WIDTHS
from module import symbols
from session_shared import into_hall


@session_scenario(starts=("entrance", "entrance"))
def widescreen_partner_wider(run):
    """A plays at 4:3 and B at 21:9 in a shared room: B's view is wide, A's isn't, and A's game (the
    room's authority) keeps the stage's enemies alive across B's view. When B goes back to 4:3, so
    do A's windows."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.expect((a.mailbox("self_presence").role, b.mailbox("self_presence").role) == (ROLE_AUTHORITY, ROLE_GUEST),
               "A is the hall's authority, B its guest")
    windows = symbols()["g_CoopWideWindows"]
    b.host("set_player", options=2 << OPT_WIDE_SHIFT)
    run.step(30)
    run.expect(b.screenshot().size == (WIDE_WIDTHS[2], WIDE_LINES), "B's view is 21:9", size=b.screenshot().size)
    run.expect(a.screenshot().size == (256, 240), "A's is 4:3", size=a.screenshot().size)
    run.expect(b.mailbox("partner_presence").wide == 0 and a.mailbox("partner_presence").wide == 2,
               "each game knows the other's shape")
    run.expect(a.read(windows, "<i") == WIDE_WIDTHS[2], "A's enemies live across B's view",
               windows=a.read(windows, "<i"))
    from coop_env import TOOLS
    run.step(120)
    b.screenshot().save(TOOLS["out"] / run.name / "b_21_9.png")  # (the out folder: game art, never in git)
    b.host("set_player", options=0)
    run.step(30)
    run.expect(a.read(windows, "<i") == 0 and b.screenshot().size == (256, 240), "both 4:3 again",
               windows=a.read(windows, "<i"), size=b.screenshot().size)
