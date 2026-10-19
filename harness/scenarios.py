"""Test scenarios. Each one starts from a savestate built by savestates.py."""

from bots import walker
from module import COOP_DISC, COOP_MAGIC, coop_state
from session import COOP  # noqa: F401  (puts `link` on the path)
from link.mailbox import LINK_VERSION
from scenario import scenario


@scenario(start="entrance")
def walk_entrance_rooms(run):
    """Alucard (no gear, after Death) walks left from Death's room through two more rooms."""
    s = run.emu.snapshot()
    run.expect(s["room"] == (20, 39) and s["stage"] == 0x41, "starts in Death's room (NO3 20,39)", room=s["room"])

    bot = walker("left", attack_every=8)
    s = run.play(bot, 600, until=lambda s: s["room"] == (14, 40))
    run.expect(s["room"] == (14, 40), "reaches the hall (14,40)", room=s["room"], frame=s["frame"])
    x0 = s["world_x"]

    s = run.play(bot, 600)
    run.expect(s["world_x"] < x0 - 100, "makes progress left through the hall", world_x=s["world_x"], start_x=x0)

    s = run.play(bot, 4000, until=lambda s: s["room"] == (11, 40))
    run.expect(s["room"] == (11, 40), "reaches the water room (11,40)", room=s["room"], frame=s["frame"])
    run.expect(s["hp"] > 0 and s["game_state"] == 2, "is alive and in play", hp=s["hp"])


@scenario(start=None, disc=COOP_DISC)
def loader_from_boot(run):
    """M1 criterion 1: COOP.BIN is loaded by CoopBoot (module/boot.c) at the start of MainGame,
    so the module runs from the very first game frame, with no familiar involved."""
    e = run.emu
    run.expect(len(e.ram) == 8 << 20, "emulator exposes 8MB of RAM", ram=len(e.ram))
    run.step(1800)  # boot to the title screen
    magic, version, beat = coop_state(e)
    run.expect(magic == COOP_MAGIC and version == LINK_VERSION, "module resident at its 8MB address", magic=hex(magic))
    run.expect(e.read("g_GameState") == 1, "the game reached the title screen", state=e.read("g_GameState"))
    run.expect(beat == e.read("g_Timer") > 0, "heartbeat has ticked every game frame since boot",
               heartbeat=beat, g_Timer=e.read("g_Timer"))


@scenario(start="entrance", disc=COOP_DISC)
def loader_in_game(run):
    """M1 criterion 1, in play: after boot, new game and the prologue (savestates.py on the co-op
    disc), the module still ticks once per game frame."""
    e = run.emu
    beat0, timer0 = coop_state(e)[2], e.read("g_Timer")
    run.expect(beat0 == timer0, "heartbeat matches g_Timer at the castle entrance", heartbeat=beat0, g_Timer=timer0)
    s = run.play(walker("right", attack_every=16), 600)
    beats, frames = coop_state(e)[2] - beat0, e.read("g_Timer") - timer0
    run.expect(beats == frames == 600, "heartbeat ticks once per game frame", beats=beats, frames=frames)
    run.expect(s["game_state"] == 2 and s["hp"] > 0, "game keeps running normally", state=s["game_state"], hp=s["hp"])
