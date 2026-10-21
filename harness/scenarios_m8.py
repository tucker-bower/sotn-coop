"""M8 and M8b scenarios (design/M8-maria-and-richter.md, design/M8b-character-balance.md): one
game on the co-op disc, playing as Richter in Alucard's castle."""

from bots import walker
from coop_env import REPO
from emu import SYMBOLS
from link.adapter import HarnessAdapter
from link.mailbox import (BUSY, CHAR_ALUCARD, CHAR_RICHTER, CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW,
                          IN_PLAY, OPT_SHORTCUTS, Mailbox)
from module import COOP_DISC, symbols
from scenario import scenario
import savestates as route

# include/game.h: RelicIds, and g_Status's fields (relics[] is its first member)
SOUL_OF_BAT, FIRE_OF_BAT, ECHO_OF_BAT, SOUL_OF_WOLF = 0, 1, 2, 4
FORM_OF_MIST, POWER_OF_MIST, GRAVITY_BOOTS, LEAP_STONE = 7, 8, 12, 13
RELIC_ON = 3  # found + active
STATUS = SYMBOLS["g_Status"]
LEVEL, EXP = STATUS + (0x80097BE8 - 0x80097964), STATUS + (0x80097BEC - 0x80097964)
HP_MAX = STATUS + 0x240
RICHTER_OVERLAY = 0x8013C000
LIB = 0x02
LESSER_DEMON_BARS = (LIB, 0, 1100, 700)  # launcher/bossstarts.py: the bars you pass in mist form


def mailbox(run):
    return Mailbox(HarnessAdapter(run.emu), symbols()["g_CoopLink"])


def wait(run, cond, frames, what, p1=0):
    for _ in range(frames):
        if cond():
            return
        run.step(1, p1)
    run.expect(False, what)


def reload_as(run, mb, character):
    """A joint save and its load with this game's character set: how Continue switches it."""
    e = run.emu
    mb.set_character(character)
    seq, p = mb.save_seq(), mb.self_presence()
    mb.command(CMD_SAVE_NOW, p.stage, 0, p.room_left, p.room_top)
    wait(run, lambda: mb.save_seq() != seq, 3000, "the save came")
    mb.put_save(mb.save_out())
    mb.command(CMD_LOAD_SAVE)
    wait(run, lambda: e.read("g_GameState") == route.GAME_NOW_LOADING, 600, "the load started")
    playing = lambda: (e.read("g_GameState") == route.GAME_PLAY and mb.self_presence().flags & IN_PLAY
                       and not mb.self_presence().flags & BUSY)
    wait(run, playing, 3000, "the load finished")
    run.step(30)


def rise(run, inputs):
    """How high (px) the player gets above the start while the inputs play, then lands."""
    e = run.emu
    y0, best = e.snapshot()["world_y"], 0
    for b in inputs:
        run.step(1, b)
        best = max(best, y0 - e.snapshot()["world_y"])
    run.step(60)
    return best


@scenario(start="entrance", disc=COOP_DISC)
def m8_richter_in_the_castle(run):
    """M8 §1: an Alucard save loads as Richter (our COOPRIC.BIN), the world stays Alucard's, and
    back as Alucard."""
    e, mb = run.emu, mailbox(run)
    ours = REPO / "build/coop/ric/COOPRIC.BIN"
    reload_as(run, mb, CHAR_RICHTER)
    run.expect(mb.self_presence().character == CHAR_RICHTER, "the game reports Richter",
               character=mb.self_presence().character)
    run.expect(e.read("g_PlayableCharacter") == 0, "the world still sees Alucard",
               g_PlayableCharacter=e.read("g_PlayableCharacter"))
    if ours.exists():
        run.expect(e.read_bytes(RICHTER_OVERLAY, 64) == ours.read_bytes()[:64],
                   "Richter's slot holds our Richter (COOPRIC.BIN)")
    x0 = e.snapshot()["world_x"]
    s = run.play(walker("left", attack_every=12), 300)
    run.expect(s["world_x"] < x0 - 50 and s["hp"] > 0, "Richter walks and whips in the castle",
               moved=x0 - s["world_x"])
    reload_as(run, mb, CHAR_ALUCARD)
    run.expect(mb.self_presence().character == CHAR_ALUCARD, "and loads back as Alucard",
               character=mb.self_presence().character)


@scenario(start="entrance", disc=COOP_DISC)
def m8b_relic_gates(run):
    """M8b criteria 1 and 6: the high jump needs Gravity Boots; L2 does it only with the player's
    shortcuts on. (The other gates are the same check in our Richter: COOP_CAN.)"""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_RICHTER)
    start = e.save_state()
    high_jump = ["down"] * 3 + [""] * 2 + ["up"] * 2 + ["up+cross"] * 2 + [""] * 60
    l2 = ["l2"] * 2 + [""] * 60
    plain = rise(run, high_jump)
    e.load_state(start)
    e.write(STATUS, RELIC_ON, "<B", GRAVITY_BOOTS)
    boots = rise(run, high_jump)
    run.expect(plain < 60 < boots, "the high jump needs Gravity Boots", without=plain, with_boots=boots)
    e.load_state(start)
    e.write(STATUS, RELIC_ON, "<B", GRAVITY_BOOTS)
    off = rise(run, l2)
    e.load_state(start)
    e.write(STATUS, RELIC_ON, "<B", GRAVITY_BOOTS)
    mb.set_options(OPT_SHORTCUTS)
    run.step(2)
    on = rise(run, l2)
    run.expect(off < 20 and on > 150, "L2 high-jumps only with shortcuts on", off=off, on=on)


@scenario(start="entrance", disc=COOP_DISC)
def m8b_growth(run):
    """M8b criterion 5: Richter levels up from EXP like Alucard (HP grows too)."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_RICHTER)
    level, hp = e.read(LEVEL), e.read(HP_MAX)
    e.write(EXP, 5000)
    run.step(30)
    run.expect(e.read(LEVEL) > level and e.read(HP_MAX) > hp, "Richter levels up",
               level=(level, e.read(LEVEL)), hp_max=(hp, e.read(HP_MAX)))


@scenario(start="entrance", disc=COOP_DISC)
def m8b_mist_step(run):
    """M8b criterion 2: Richter passes the bars before the Lesser Demon with Form of Mist, and
    can't without it."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_RICHTER)
    start = e.save_state()
    for relic in (False, True):
        e.load_state(start)
        if relic:
            e.write(STATUS, RELIC_ON, "<B", FORM_OF_MIST)
        mb.command(CMD_ARRIVE, *LESSER_DEMON_BARS)
        wait(run, lambda: (lambda p: p.stage == LIB and p.flags & IN_PLAY and not p.flags & BUSY)(
            mb.self_presence()), 900, "arrived in the Long Library")
        run.step(60)
        xs = []
        for i in range(600):
            route.heal(e)
            run.step(1, "left+cross" if i % 60 < 20 and i < 200 else "left")
            xs.append(mb.self_presence().x)
        if relic:
            run.expect(min(xs) < 700, "with Form of Mist, Richter is past the bars", x=min(xs))
        else:
            run.expect(min(xs) > 760, "without it, the bars stop him", x=min(xs))
