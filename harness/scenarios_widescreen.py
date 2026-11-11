"""Widescreen (design/M19-widescreen.md): one game, the player's screen shape."""

from link.adapter import HarnessAdapter
from link.mailbox import OPT_WIDE_SHIFT, WIDE_SHAPES, WIDE_WIDTHS, Mailbox
from module import COOP_DISC, symbols
from scenario import scenario

MENU_OPEN = 2  # g_GameEngineStep: the pause menu


@scenario(start="nz0", disc=COOP_DISC)
def widescreen_shape_option(run):
    """The screen shape in a player's options sets the game's view: 256, 352 or 448 wide, as tall as
    ever. The pause menu is drawn as the game draws it (the core back at 4:3), and the view comes back
    wide when it closes. 4:3 is the game as it was."""
    e = run.emu
    mb = Mailbox(HarnessAdapter(e), symbols()["g_CoopLink"])
    for shape, width in zip(range(len(WIDE_SHAPES)), WIDE_WIDTHS):
        mb.set_options(shape << OPT_WIDE_SHIFT)
        run.step(10)
        size = e.screenshot().size
        run.expect(size == (width, 240), f"{WIDE_SHAPES[shape]}: the view is {width} wide", size=size)
    mb.set_options(1 << OPT_WIDE_SHIFT)
    run.step(10)
    run.step(4, "start")
    run.step(90)
    run.expect(e.read("g_GameEngineStep") == MENU_OPEN, "the pause menu is open")
    run.expect(e.screenshot().size[0] != 352, "the menu isn't drawn at the wide width", size=e.screenshot().size)
    for _ in range(6):
        run.step(2, "triangle")
        run.step(30)
        if e.read("g_GameEngineStep") == 1:
            break
    run.step(30)
    run.expect(e.screenshot().size == (352, 240), "closed: wide again", size=e.screenshot().size)
    mb.set_options(0)
    run.step(10)
    run.expect(e.screenshot().size == (256, 240), "4:3 again in play: the game's own view", size=e.screenshot().size)
