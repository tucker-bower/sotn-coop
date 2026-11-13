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


# --- #260: at 21:9 a red door spawned in the extra width was destroyed at once and never came back ---
DESTROY_OUT, BARELY_OUT = 0x80000000, 0x40000000  # FLAG_DESTROY_IF_OUT_OF_CAMERA, ..._BARELY_...


def _wide(e, shape):
    Mailbox(HarnessAdapter(e), symbols()["g_CoopLink"]).set_options(shape << OPT_WIDE_SHIFT)
    e.step(5)


def _stage_entities(e):
    """{slot: (entityId, flags)} of the stage's entities (64..255)."""
    import struct
    raw = e.read_bytes("g_Entities", 0xBC * 256)
    out = {}
    for slot in range(64, 256):
        b = raw[slot * 0xBC:(slot + 1) * 0xBC]
        if struct.unpack_from("<I", b, 0x28)[0] and struct.unpack_from("<H", b, 0x2C)[0]:  # pfnUpdate, step
            out[slot] = (struct.unpack_from("<H", b, 0x26)[0], struct.unpack_from("<I", b, 0x34)[0])
    return out


@scenario(start="nz0", disc=COOP_DISC)
def widescreen_stage_windows_every_stage(run):
    """In every debug start's stage, at 21:9, an entity the game destroys off camera lives anywhere
    the spawner brings things in (the view's extra width past the game's -64..320): each stage's
    Update windows are widened as its spawner's are, in their signed and unsigned forms (#260)."""
    from coop_env import TOOLS
    e = run.emu
    starts = TOOLS["out"].parent / "fixtures" / "debug-starts"
    extra = WIDE_WIDTHS[2] - 256
    seen, bad, tried = set(), [], []
    for state in sorted(starts.glob("*.state")):
        e.load_state_file(str(state))
        e.step(2)
        stage = e.snapshot()["stage"]
        if stage in seen:
            continue
        seen.add(stage)
        _wide(e, 2)
        ents = {s: v for s, v in _stage_entities(e).items() if v[1] & DESTROY_OUT}
        for slot, (eid, flags) in list(ents.items())[:3]:
            for x in (320 + extra - 8, -64 - extra + 8):
                e.load_state_file(str(state))
                _wide(e, 2)
                if _stage_entities(e).get(slot, (None,))[0] != eid:
                    continue
                at = e.entity(slot)
                e.write(at, x, "<h", 2)
                e.write(at, 0, "<i", 8)  # velocityX: it stays where it's put for the frame
                e.step(1)
                tried.append((state.stem, slot))
                if _stage_entities(e).get(slot, (None,))[0] != eid:
                    bad.append((state.stem, stage, slot, hex(eid), hex(flags), x))
    run.expect(len(tried) >= 20, "entities tried in many stages", tried=len(tried), stages=sorted(seen))
    run.expect(not bad, "each lives where the wide spawner brings things in", bad=bad[:12], count=len(bad))


@scenario(start="nz0", disc=COOP_DISC)
def widescreen_red_door_comes_back(run):
    """The Alchemy Lab's first room at 16:9 and 21:9: walk away from its red door and back, and the
    door is there and opens into the next room (#260: at 21:9 it vanished once it had spawned in the
    extra width, and the player couldn't leave)."""
    from bots import walker
    from coop_env import TOOLS
    e = run.emu
    state = TOOLS["out"].parent / "fixtures" / "debug-starts" / "Alchemy Laboratory.state"
    for shape in (1, 2):
        e.load_state_file(str(state))
        _wide(e, shape)
        room = e.snapshot()["room"]
        bot = walker("left", jump_when_stuck=False)
        for i in range(170):
            run.step(1, bot(e.snapshot(), i))
        bot, through = walker("right"), None
        for i in range(600):
            run.step(1, bot(e.snapshot(), i))
            if e.snapshot()["room"] != room:
                through = i
                break
        run.expect(through is not None, f"{WIDE_SHAPES[shape]}: back through the door into the next room",
                   at=e.snapshot(), doors=[s for s, v in _stage_entities(e).items() if v[0] == 5])
