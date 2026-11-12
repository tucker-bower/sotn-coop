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


@scenario(start="nz0", disc=COOP_DISC)
def widescreen_fade(run):
    """The screen fade (going to another stage) darkens the whole wide view, not only the game's
    256 in its middle: while the middle is dark, the edges are too."""
    from PIL import ImageStat
    from link.mailbox import CMD_ARRIVE
    e = run.emu
    mb = Mailbox(HarnessAdapter(e), symbols()["g_CoopLink"])
    mb.set_options(2 << OPT_WIDE_SHIFT)
    run.step(10)
    room, worst = e.snapshot()["room"], None
    mb.command(CMD_ARRIVE, 0x00, 0, 128, 136)  # the Marble Gallery
    for i in range(900):
        run.step(1)
        img = e.screenshot()
        if img.size[0] != WIDE_WIDTHS[2]:
            continue
        w = img.size[0]
        middle = ImageStat.Stat(img.crop((w // 2 - 64, 0, w // 2 + 64, img.size[1])).convert("L")).mean[0]
        edges = max(ImageStat.Stat(img.crop(box).convert("L")).mean[0] for box in ((0, 0, 40, img.size[1]), (w - 40, 0, w, img.size[1])))
        if middle < 4:  # faded out
            worst = edges if worst is None else max(worst, edges)
        if e.snapshot()["room"] != room and worst is not None:
            break
    run.expect(worst is not None, "a room change faded the view")
    run.expect(worst < 8, "the edges faded with the middle", brightest_edge=worst)
