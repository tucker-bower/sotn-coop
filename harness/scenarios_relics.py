"""M12 v1.0 coverage (design/M12-v1-release.md criterion 1): relics, per character.

Richter's and Maria's relic-gated moves are M8b's (`m8b_relic_gates`, `m8b_more_gates`,
`m8b_mist_step`, `m8b_poison_water`). Here: Alucard's own relics (his forms and their upgrades),
the Vlad relics for everyone, and every familiar card for everyone. Each relic is measured without
it and with it, from the same savestate; a report per test lands in .env/out/<test>/relics.json."""

import json

from coop_env import TOOLS
from link.mailbox import BUSY, CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CMD_ARRIVE, IN_PLAY
from module import COOP_DISC
from scenario import scenario
from scenarios_m8 import (HALL_ROOM, NO3, RELIC_ON, SERVANT, SERVANT_LOADED, STATUS, mailbox, reload_as, rise,
                          travel, wait)

# include/game.h RelicIds
(SOUL_OF_BAT, FIRE_OF_BAT, ECHO_OF_BAT, FORCE_OF_ECHO, SOUL_OF_WOLF, POWER_OF_WOLF, SKILL_OF_WOLF,
 FORM_OF_MIST, POWER_OF_MIST, GAS_CLOUD) = range(10)
GRAVITY_BOOTS, LEAP_STONE = 12, 13
CARDS = {18: "bat", 19: "ghost", 20: "faerie", 21: "demon", 22: "sword"}  # BAT_CARD..SWORD_CARD
HEART_OF_VLAD, TOOTH_OF_VLAD, RIB_OF_VLAD, RING_OF_VLAD, EYE_OF_VLAD = range(25, 30)
# include/player_steps.h
MORPH_BAT, MORPH_MIST, MORPH_WOLF = 5, 7, 24
# g_Status (include/game.h)
MP, MP_MAX = 0x80097BB0, 0x80097BB4
STATS_EQUIP = 0x80097BC8  # STR, CON, INT, LCK
ELEMENTS_IMMUNE, ELEMENT_CURSE = 0x80097C2C, 0x100
STEP = 0x2C  # Entity.step


def to_the_hall(run, mb):
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)  # room to move: the castle entrance's zombie hall
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    run.step(90)


def report(run, rows):
    (TOOLS["out"] / run.name).mkdir(parents=True, exist_ok=True)
    (TOOLS["out"] / run.name / "relics.json").write_text(json.dumps(rows, indent=1))


def player_ids(e):
    """(slot, entity id) of everything in the player's slots 4-63 now."""
    return {(s, e.read(e.entity(s), "<H", 0x26)) for s in range(4, 64) if e.read(e.entity(s), "<H", 0x26)}


def frames_in(run, inputs, steps):
    """How many frames the player spends in one of these steps while the inputs play."""
    n = 0
    for b in inputs:
        run.step(1, b)
        n += run.emu.read(run.emu.entity(0), "<H", STEP) in steps
    return n


def spawned(run, inputs, then):
    """How many new entities appear in the player's slots during `then`, after `inputs` set up."""
    for b in inputs:
        run.step(1, b)
    before, seen = player_ids(run.emu), set()
    for b in then:
        run.step(1, b)
        seen |= player_ids(run.emu) - before
    return len(seen)


def mp_spent(run, inputs):
    e = run.emu
    mp = e.read(MP, "<i")
    for b in inputs:
        run.step(1, b)
    return mp - e.read(MP, "<i")


BAT, MIST, WOLF = ["r1"] * 2 + [""] * 40, ["l1"] * 2 + [""] * 30, ["r2"] * 2 + [""] * 40
QCF = ["down"] * 3 + ["down+right"] * 3 + ["right"] * 2 + ["right+square"] * 2 + [""] * 60

# (what, relics without, relics with, measure(run), at least this much more with the relic)
ALUCARD_ROWS = [
    ("Soul of Bat: R1 turns into a bat", [], [SOUL_OF_BAT], lambda r: frames_in(r, BAT, {MORPH_BAT}), 20),
    ("Form of Mist: L1 turns into mist", [], [FORM_OF_MIST], lambda r: frames_in(r, MIST, {MORPH_MIST}), 15),
    ("Soul of Wolf: R2 turns into a wolf", [], [SOUL_OF_WOLF], lambda r: frames_in(r, WOLF, {MORPH_WOLF}), 20),
    ("Leap Stone: the double jump", [], [LEAP_STONE],
     lambda r: rise(r, ["cross"] * 16 + [""] * 2 + ["cross"] * 12 + [""] * 60), 12),
    ("Gravity Boots: the super jump", [], [GRAVITY_BOOTS],
     lambda r: rise(r, ["down"] * 3 + [""] * 2 + ["up"] * 2 + ["up+cross"] * 2 + [""] * 60), 60),
    ("Echo of Bat: the bat's sonar (triangle)", [SOUL_OF_BAT], [SOUL_OF_BAT, ECHO_OF_BAT],
     lambda r: spawned(r, BAT, ["triangle"] * 2 + [""] * 30), 1),
    ("Fire of Bat: the bat's fireball (square)", [SOUL_OF_BAT], [SOUL_OF_BAT, FIRE_OF_BAT],
     lambda r: mp_spent(r, BAT + ["square"] * 2 + [""] * 30), 1),
    ("Power of Mist: mist lasts", [FORM_OF_MIST], [FORM_OF_MIST, POWER_OF_MIST],
     lambda r: frames_in(r, ["l1"] * 2 + ["l1"] * 400, {MORPH_MIST}), 30),
    ("Gas Cloud: poison mist", [FORM_OF_MIST], [FORM_OF_MIST, GAS_CLOUD], lambda r: spawned(r, [], MIST + [""] * 30), 1),
]


# Not measured yet, with the reason (criterion 1 allows a listed problem): kept in the report.
ALUCARD_GAPS = [
    {"what": "Power of Wolf: the wolf runs faster", "why": "the wolf's dash (WolfStepS_2 case 2) isn't reached by "
     "holding a direction in the test hall, and the hall's zombies end the form after about 2 s"},
    {"what": "Skill of Wolf: the wolf's charge", "why": "starts from the same dash (func_8012CC30)"},
]


def measure_rows(run, start, rows):
    e, got = run.emu, []
    for what, base, more, how, margin in rows:
        out = []
        for relics in (base, more):
            e.load_state(start)
            for r in relics:
                e.write(STATUS, RELIC_ON, "<B", r)
            e.write(MP, e.read(MP_MAX, "<i"), "<i")
            run.step(2)
            out.append(how(run))
        got.append({"what": what, "without": out[0], "with": out[1], "ok": out[1] >= out[0] + margin})
    return got


@scenario(start="entrance", disc=COOP_DISC)
def m12_relics_alucard(run):
    """Alucard's own relics: each form and each of its upgrades does nothing without its relic and
    works with it (the game's own code; a regression check for everything the module hooks)."""
    e, mb = run.emu, mailbox(run)
    to_the_hall(run, mb)
    got = measure_rows(run, e.save_state(), ALUCARD_ROWS)
    report(run, got + [dict(g, ok=None) for g in ALUCARD_GAPS])
    bad = [g for g in got if not g["ok"]]
    run.expect(not bad, f"every relic ({len(got)}) works only with it", bad=bad)


NAMES = {CHAR_ALUCARD: "alucard", CHAR_RICHTER: "richter", CHAR_MARIA: "maria"}


def per_character(fn):
    """Registers fn(run, character) as <name>_alucard, _richter and _maria."""
    for ch, name in NAMES.items():
        def one(run, ch=ch):
            return fn(run, ch)
        one.__name__ = f"{fn.__name__}_{name}"
        one.__doc__ = fn.__doc__
        scenario(start="entrance", disc=COOP_DISC)(one)
    return fn


@per_character
def m12_vlad_relics(run, ch):
    """Dracula's relics, for every character: +10 to a stat each (Tooth STR, Rib CON, Ring INT, Eye
    LCK), and the Heart makes the player immune to curses."""
    e, mb = run.emu, mailbox(run)
    start = e.save_state()

    def with_relic(relic):
        """The status after a load with the relic on (the game works stats out on a load and in
        the menu, not every frame)."""
        e.load_state(start)
        if relic is not None:
            e.write(STATUS, RELIC_ON, "<B", relic)
        reload_as(run, mb, ch)
        return [e.read(STATS_EQUIP + 4 * i, "<i") for i in range(4)], e.read(ELEMENTS_IMMUNE, "<H") & ELEMENT_CURSE
    base, cursed = with_relic(None)
    got = []
    for relic, stat, name in ((TOOTH_OF_VLAD, 0, "Tooth: STR"), (RIB_OF_VLAD, 1, "Rib: CON"),
                              (RING_OF_VLAD, 2, "Ring: INT"), (EYE_OF_VLAD, 3, "Eye: LCK")):
        now = with_relic(relic)[0]
        got.append({"what": f"{name} +10", "without": base[stat], "with": now[stat], "ok": now[stat] == base[stat] + 10})
    immune = with_relic(HEART_OF_VLAD)[1]
    got.append({"what": "Heart: immune to curses", "without": cursed, "with": immune, "ok": not cursed and immune})
    report(run, got)
    bad = [g for g in got if not g["ok"]]
    run.expect(not bad, f"every Vlad relic works for {NAMES[ch].capitalize()}", bad=bad)


@per_character
def m12_familiars(run, ch):
    """Every familiar card, for every character (M8b §3 tested the bat and the ghost): with the card
    on and a load, the familiar is loaded, comes out, and the player still plays."""
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    got = []
    for fam, (relic, name) in enumerate(CARDS.items(), 1):
        e.load_state(start)
        e.write(STATUS, RELIC_ON, "<B", relic)
        reload_as(run, mb, ch)
        run.step(300)
        ids = [e.read(e.entity(s), "<H", 0x26) for s in range(4, 64)]
        loaded = e.read(SERVANT) == fam and e.read(SERVANT_LOADED) == fam
        out = any(0xD0 <= i < 0xE0 for i in ids)
        s0 = e.snapshot()
        for i in range(300):
            run.step(1, "left" if i % 120 < 60 else "right+square" if i % 12 == 0 else "right")
        s = e.snapshot()
        plays = s["hp"] > 0 and (s["world_x"] != s0["world_x"] or s["room"] != s0["room"])
        got.append({"what": name, "loaded": loaded, "out": out, "plays": plays, "ok": loaded and out and plays})
    report(run, got)
    bad = [g for g in got if not g["ok"]]
    run.expect(not bad, f"all 5 familiars work for {NAMES[ch].capitalize()}", bad=bad)


# --- subweapons and item crashes ------------------------------------------------------------
SUBWEAPON, HEARTS, HEARTS_MAX = 0x80097BFC, 0x80097BA8, 0x80097BAC  # g_Status
SUBWEAPONS = range(1, 10)  # SUBWPN_DAGGER..SUBWPN_AGUNEA (include/game.h): the castle's pickups
# Maria has guardians, not Alucard's subweapons: the Maria port's glue (mods/mariapsp-forpsx/maria.c)
# turns the dagger, axe, holy water and vibhuti into the cat, cardinal, turtle and dragon, and the
# others keep the guardian she has, with a heart back (D118: the bible too; it used to leave her none).
MARIA_GUARDIAN = {1: 1, 2: 2, 3: 3, 8: 8}  # the ones that change her guardian (Alucard ids, as stored)


def use_subweapon(run, inputs):
    """(hearts spent, new entities in the player's slots) while the inputs play, then 90 frames."""
    e = run.emu
    e.write(HEARTS_MAX, 200, "<i")
    e.write(HEARTS, 200, "<i")  # Alucard's cross costs 100
    before, seen = player_ids(e), set()
    for b in inputs + [""] * 90:
        run.step(1, b)
        seen |= player_ids(e) - before
    return 200 - e.read(HEARTS, "<i"), len(seen)


def subweapon_sweep(run, ch, inputs, relics=()):
    e, mb = run.emu, mailbox(run)
    if ch != CHAR_ALUCARD:
        reload_as(run, mb, ch)
    to_the_hall(run, mb)
    start = e.save_state()
    got = []
    for sub in SUBWEAPONS:
        e.load_state(start)
        for r in relics:
            e.write(STATUS, RELIC_ON, "<B", r)
        if ch == CHAR_MARIA:  # as a pickup: she holds the cat (the dagger) first
            e.write(SUBWEAPON, 1, "<i")
            run.step(5)
        e.write(SUBWEAPON, sub, "<i")
        run.step(5)
        holds = e.read(SUBWEAPON, "<i")
        hearts, made = use_subweapon(run, inputs)
        alive = e.snapshot()["hp"] > 0 and e.read("g_GameState") == 2  # still playing
        kept = ch != CHAR_MARIA or holds == MARIA_GUARDIAN.get(sub, 1)
        got.append({"subweapon": sub, "holds": holds, "hearts": hearts, "entities": made, "playing": alive,
                    "ok": hearts > 0 and made > 0 and alive and kept})
    report(run, got)
    return got


@per_character
def m12_subweapons(run, ch):
    """Every subweapon the castle has (1-9), thrown by every character (up + attack): it costs
    hearts, makes its entities, and the game plays on. For Maria, each is picked up while she holds
    the cat: four become a guardian, the rest leave her the cat (MARIA_GUARDIAN, D118)."""
    got = subweapon_sweep(run, ch, ["up+square"] * 2)
    bad = [g for g in got if not g["ok"]]
    run.expect(not bad, f"every subweapon works for {NAMES[ch].capitalize()}", bad=bad)


def _crashes(run, ch):
    """Every item crash (Richter) and guardian crash (Maria), with Echo of Bat (M8b §3): triangle
    spends the crash's hearts and makes its entities, for every subweapon."""
    got = subweapon_sweep(run, ch, ["triangle"] * 2, relics=(ECHO_OF_BAT,))
    bad = [g for g in got if not g["ok"]]
    run.expect(not bad, f"every crash works for {NAMES[ch].capitalize()}", bad=bad)


for _ch in (CHAR_RICHTER, CHAR_MARIA):
    def _one(run, ch=_ch):
        return _crashes(run, ch)
    _one.__name__ = f"m12_crashes_{NAMES[_ch]}"
    _one.__doc__ = _crashes.__doc__
    scenario(start="entrance", disc=COOP_DISC)(_one)
