"""Test scenarios. Each one starts from a savestate built by savestates.py."""

from bots import walker
from module import COOP_DISC, COOP_MAGIC, coop_state, symbols
from savestates import warp
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


RELIC_BAT_CARD = 18  # index into g_Status.relics
RELIC_FOUND_ACTIVE = 3


@scenario(start="entrance", disc=COOP_DISC)
def heartbeat_8mb(run):
    """M0 module (TT_000 slot, see module/inject.c) installs itself in the 8MB area and runs every frame.
    The familiar slot only loads when a familiar is active, so the harness turns the Bat Card on."""
    e = run.emu
    run.expect(len(e.ram) == 8 << 20, "emulator exposes 8MB of RAM", ram=len(e.ram))
    run.expect(coop_state(e)[0] != COOP_MAGIC, "module not resident before the familiar loads")

    e.write(e.addr("g_Status") + RELIC_BAT_CARD, RELIC_FOUND_ACTIVE, "<B")
    warp(e, 0x0C)
    magic, version, beat0 = coop_state(e)
    run.expect(magic == COOP_MAGIC and version == 1, "module resident at its 8MB address", magic=hex(magic))
    run.expect(e.read(0x800E3D00) == 0x0C000000 | ((symbols()["CoopMainLoop"] & 0x3FFFFFF) >> 2),
               "main loop calls CoopMainLoop")

    s = run.play(walker("right", attack_every=16), 600)
    beat = coop_state(e)[2]
    run.expect(590 <= beat - beat0 <= 600, "heartbeat ticks once per game frame", beats=beat - beat0, frames=600)
    run.expect(s["game_state"] == 2 and s["hp"] > 0, "game keeps running normally", state=s["game_state"], hp=s["hp"])
