"""M12 fixtures (design/M12-coverage.md): savestates the coverage tests start from, made from the
user's own co-op disc like the library in savestates.py (game RAM: never committed).

    python fixtures_m12.py [name ...]      (default: all)

  st0_start   the prologue's first frame in play (Richter walking into Dracula's throne room)
  st0_fight   the prologue's opening scene over: Richter in the throne room, the fight on
  st0_end     Dracula just fell: the prologue's ending (game state 3) starts
  no3_start   the first frame in the castle (NO3) after the real prologue (not skip_prologue)
"""

import sys

from coop_env import savestate
from emu import Emu
from module import COOP_DISC
from savestates import GAME_PLAY, STAGE_ST0, wait_until
from session_m12 import fight_pad


def st0_start(e):
    # new_game without its last 600 frames: stop at the first frame of play in ST0
    wait_until(e, lambda: e.read("g_GameState") == 1, 6000, "title screen")
    e.step(600)
    e.step(2, "start"); e.step(360)
    e.step(2, "cross"); e.step(300)
    e.step(2, "cross"); e.step(120)
    e.step(2, "cross"); e.step(20)
    e.step(2, "start")
    wait_until(e, lambda: e.read("g_GameState") == GAME_PLAY and e.read("g_StageId") == STAGE_ST0, 12000,
               "prologue gameplay")


def st0_fight(e):
    st0_start(e)
    wait_until(e, lambda: e.read("g_CutsceneHasControl"), 3000, "the opening scene", p1="up+left")
    e.step(600, "up+left")  # off the stairs: the scene steers Richter from there
    wait_until(e, lambda: not e.read("g_CutsceneHasControl"), 6000, "the opening scene's end")


def st0_end(e):
    st0_fight(e)
    for t in range(20000):  # a plain whip bot, with Dracula worn down (the fixture, not a test)
        if e.read("g_GameState") == 3:
            return
        if t % 30 == 0:
            for slot in range(64, 256):
                hp = e.read("g_Entities", "<h", slot * 0xBC + 0x3E)
                if 8 < hp < 32767 and e.read("g_Entities", "<H", slot * 0xBC + 0x26):
                    e.write("g_Entities", 8, "<h", slot * 0xBC + 0x3E)
        e.step(1, fight_pad(e, t=t))
    raise RuntimeError("Dracula never fell")


def no3_start(e):
    st0_end(e)
    for t in range(20000):
        if e.read("g_StageId") == 0x41 and e.read("g_GameState") == GAME_PLAY:
            return
        e.step(1, "start" if t % 120 < 2 else "")  # skip through the prologue's ending
    raise RuntimeError(f"never reached the castle: {e.snapshot()}")


FIXTURES = {"st0_start": st0_start, "st0_fight": st0_fight, "st0_end": st0_end, "no3_start": no3_start}


def build(names=None, disc=COOP_DISC):
    for name in names or FIXTURES:
        with Emu(disc) as e:
            FIXTURES[name](e)
            path = savestate(disc, name)
            e.save_state_file(path)
            e.screenshot(path.with_suffix(".png"))
            print(name, e.snapshot(), flush=True)


if __name__ == "__main__":
    build(sys.argv[1:])
