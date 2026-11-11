"""Widescreen (design/M19-widescreen.md): one game, the player's screen shape."""

from link.adapter import HarnessAdapter
from link.mailbox import OPT_WIDE_SHIFT, WIDE_LINES, WIDE_SHAPES, WIDE_WIDTHS, Mailbox
from module import COOP_DISC, symbols
from scenario import scenario

MENU_OPEN = 2  # g_GameEngineStep: the pause menu


@scenario(start="nz0", disc=COOP_DISC)
def widescreen_shape_option(run):
    """The screen shape in a player's options sets the game's view: 4:3 as ever, or its 207 game
    lines 294 (16:9) or 392 (21:9) wide. The pause menu is shown as the game shows it (the core back
    at 4:3), and the view comes back wide when it closes. 4:3 is the game as it was."""
    e = run.emu
    mb = Mailbox(HarnessAdapter(e), symbols()["g_CoopLink"])
    for shape, width in zip(range(len(WIDE_SHAPES)), WIDE_WIDTHS):
        mb.set_options(shape << OPT_WIDE_SHIFT)
        run.step(10)
        size = e.screenshot().size
        want = (width, WIDE_LINES) if shape else (256, 240)
        run.expect(size == want, f"{WIDE_SHAPES[shape]}: the view is {want}", size=size)
    mb.set_options(1 << OPT_WIDE_SHIFT)
    run.step(10)
    run.step(4, "start")
    run.step(90)
    run.expect(e.read("g_GameEngineStep") == MENU_OPEN, "the pause menu is open")
    run.expect(e.screenshot().size[1] == 240, "the menu is shown as the game shows it", size=e.screenshot().size)
    for _ in range(6):
        run.step(2, "triangle")
        run.step(30)
        if e.read("g_GameEngineStep") == 1:
            break
    run.step(30)
    run.expect(e.screenshot().size == (WIDE_WIDTHS[1], WIDE_LINES), "closed: wide again", size=e.screenshot().size)
    mb.set_options(0)
    run.step(10)
    run.expect(e.screenshot().size == (256, 240), "4:3 again in play: the game's own view", size=e.screenshot().size)
