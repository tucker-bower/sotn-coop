"""Builds the savestate library from the user's own disc. Savestates hold game RAM: never commit them.

    python savestates.py [disc.cue]     -> .env/savestates/<disc>/{entrance,nz0,no0,no1}.state + index.json

Route (deterministic, ~30k frames, about 30 s at harness speed):
  boot -> File select -> New game -> name "A" -> opening video
  -> prologue skipped by RAM poke (harness only, see skip_prologue)
  -> castle entrance (NO3) played by a bot up to Death taking the gear  => "entrance"
  -> warps to Alchemy Lab, Marble Gallery and Outer Wall with the same status  => "nz0", "no0", "no1"
Every checkpoint is healed to full HP so tests don't start one hit from death.
"""

import json
import sys

from coop_env import DISKS, savestate
from emu import SYMBOLS, Emu

GAME_PLAY, GAME_NOW_LOADING, GAME_VIDEO, GAME_PROLOGUE_END = 2, 4, 5, 7
STAGE_ST0, STAGE_NO3 = 0x1F, 0x41
STATUS_SIZE = 0x334  # sizeof(PlayerStatus)
PLAY_WAIT_STAGE_PRG = 10  # g_GameStep during Game_NowLoading
EQUIPMENT = SYMBOLS["g_Status"] + 0x29C  # u32 equipment[7]; [0] is the right hand
DEATH_ROOM = (20, 39)  # NO3 room index 11: E_CUTSCENE (layout 10) runs the Death scene

WARPS = {"nz0": 0x0C, "no0": 0x00, "no1": 0x01}  # Alchemy Lab, Marble Gallery, Outer Wall


def wait_until(e, cond, limit, what, p1=0):
    for _ in range(limit):
        if cond():
            return
        e.step(1, p1)
    raise RuntimeError(f"timed out after {limit} frames waiting for {what}: {e.snapshot()}")


def new_game(e):
    """Title screen -> File select -> New game -> name 'A' -> prologue starts."""
    e.step(1800)                      # boot + title
    e.step(2, "start"); e.step(360)   # main menu
    e.step(2, "cross"); e.step(300)   # File select: memory card check
    e.step(2, "cross"); e.step(120)   # New game -> name entry
    e.step(2, "cross"); e.step(20)    # type "A"
    e.step(2, "start")                # decide
    wait_until(e, lambda: e.read("g_GameState") == GAME_VIDEO, 600, "opening video")
    wait_until(e, lambda: e.read("g_GameState") == GAME_PLAY, 9000, "prologue gameplay")
    e.step(600)


def skip_prologue(e):
    """Harness-only shortcut: does what SetGameState(Game_PrologueEnd) does when Richter's game over
    ends in ST0 (src/dra/game_handlers.c). Richter is at full HP, so Alucard gets the no-damage
    bonus (+1 STR/CON/INT/LCK, InitStatsAndGear)."""
    assert e.read("g_StageId") == STAGE_ST0
    e.write("g_GameState", GAME_PROLOGUE_END)
    e.write("g_GameStep", 0)
    wait_until(e, lambda: e.read("g_StageId") == STAGE_NO3 and e.read("g_GameState") == GAME_PLAY,
               12000, "castle entrance")


def play_to_death(e):
    """Bot: hold right and jump on a fixed rhythm until Death's room. Some rhythms drop into the
    lower dead end (room 14,41), so try rhythms from a snapshot until one works. Deterministic."""
    e.step(600)
    e.step(3000, "right")
    start = e.save_state()
    for period in (40, 36, 44, 32, 48, 28, 52, 56, 60):
        e.load_state(start)
        for i in range(8000):
            room = e.snapshot()["room"]
            if room == DEATH_ROOM or room == (14, 41):
                break
            e.step(1, "right+cross" if i % period < period // 2 else "right")
        if room == DEATH_ROOM:
            break
    else:
        raise RuntimeError(f"bot never reached Death's room: {e.snapshot()}")
    e.step(300, "right")
    wait_until(e, lambda: e.read(EQUIPMENT) == 0, 3000, "Death taking the gear")
    e.step(1800)  # cutscene ends, control returns


def heal(e):
    e.write("g_Status", e.read("g_Status", "<i", 0x240), "<i", 0x23C)  # hp = hpMax


def warp(e, stage):
    """Harness-only: loads a stage the way the debug module does, keeping the player's status.
    The Game_NowLoading path runs InitStatsAndGear at Play_WaitStagePrg, which outside NO3 applies a
    debug loadout, so the real status is put back right after it, before weapons and the familiar
    are chosen and loaded from it."""
    status = e.read_bytes("g_Status", STATUS_SIZE)
    e.write("g_LoadOvlIdx", stage)
    e.write("g_StageId", stage)
    e.write("g_GameState", GAME_NOW_LOADING)
    e.write("g_GameStep", 2)
    wait_until(e, lambda: e.read("g_GameStep") > PLAY_WAIT_STAGE_PRG, 3000, f"stage {stage:#x} program")
    a = e.addr("g_Status") & e._ram_mask
    e.ram[a:a + STATUS_SIZE] = status
    wait_until(e, lambda: e.read("g_GameState") == GAME_PLAY, 3000, f"stage {stage:#x} to load")
    e.step(300)  # stage title card


def build(disc):
    out_dir = savestate(disc, "x").parent
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {}

    def checkpoint(e, name):
        heal(e)
        e.step(1)
        e.save_state_file(out_dir / f"{name}.state")
        e.screenshot(out_dir / f"{name}.png")
        index[name] = e.snapshot()
        print(name, index[name], flush=True)

    with Emu(disc) as e:
        new_game(e)
        skip_prologue(e)
        play_to_death(e)
        checkpoint(e, "entrance")
        entrance = e.save_state()
        for name, stage in WARPS.items():
            e.load_state(entrance)
            warp(e, stage)
            checkpoint(e, name)
    (out_dir / "index.json").write_text(json.dumps(index, indent=1))
    return index


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else DISKS / "sotn.us.cue")
