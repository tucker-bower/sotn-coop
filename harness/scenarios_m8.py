"""M8 and M8b scenarios (design/M8-maria-and-richter.md, design/M8b-character-balance.md): one
game on the co-op disc, playing as Richter or Maria in Alucard's castle. Each character test is
registered once per character: <name>_richter, <name>_maria (Maria needs the dev DXC disc)."""

import struct

from bots import walker
from coop_env import REPO
from emu import SYMBOLS
from link.adapter import HarnessAdapter
from link.mailbox import (BUSY, CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW,
                          CHAR_BLOB_ADDR, IN_PLAY, OPT_SHORTCUTS, Mailbox)
from module import COOP_DISC, maria_blob, symbols
from scenario import SCENARIOS, scenario
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
    """A joint save and its load with this game's character set: how Continue switches it.
    Maria's blob goes into the 8MB RAM first, as the launcher's host does."""
    e = run.emu
    if character == CHAR_MARIA:
        blob = maria_blob()
        run.expect(blob is not None, "Maria's blob builds (dev DXC disc)")
        e.write_bytes(CHAR_BLOB_ADDR, blob)
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


NAMES = {CHAR_RICHTER: "Richter", CHAR_MARIA: "Maria"}


def per_character(fn):
    """Registers fn(run, character) as <name>_richter and <name>_maria."""
    for ch, name in NAMES.items():
        def one(run, ch=ch):
            return fn(run, ch)
        one.__name__ = f"{fn.__name__}_{name.lower()}"
        one.__doc__ = fn.__doc__
        scenario(start="entrance", disc=COOP_DISC)(one)
    return fn


@per_character
def m8_in_the_castle(run, ch):
    """M8 §1: an Alucard save loads as Richter (our COOPRIC.BIN) or Maria (her blob), the world
    stays Alucard's, and back as Alucard."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    run.expect(mb.self_presence().character == ch, f"the game reports {NAMES[ch]}",
               character=mb.self_presence().character)
    run.expect(e.read("g_PlayableCharacter") == 0, "the world still sees Alucard",
               g_PlayableCharacter=e.read("g_PlayableCharacter"))
    ours = REPO / "build/coop/ric/COOPRIC.BIN" if ch == CHAR_RICHTER else None
    if ours and ours.exists():
        run.expect(e.read_bytes(RICHTER_OVERLAY, 64) == ours.read_bytes()[:64],
                   "Richter's slot holds our Richter (COOPRIC.BIN)")
    if ch == CHAR_MARIA:
        ovl = maria_blob()[32:96]
        run.expect(e.read_bytes(RICHTER_OVERLAY, 64) == ovl, "Richter's slot holds Maria's overlay")
    s0 = e.snapshot()
    s = run.play(walker("left", attack_every=12), 300)
    run.expect((s["world_x"] < s0["world_x"] - 50 or s["room"] != s0["room"]) and s["hp"] > 0,
               f"{NAMES[ch]} walks and attacks in the castle", moved=s0["world_x"] - s["world_x"],
               room=s["room"])
    reload_as(run, mb, CHAR_ALUCARD)
    run.expect(mb.self_presence().character == CHAR_ALUCARD, "and loads back as Alucard",
               character=mb.self_presence().character)


@per_character
def m8b_relic_gates(run, ch):
    """M8b criteria 1 and 6: the high jump needs Gravity Boots; L2 does it only with the player's
    shortcuts on. (The other gates are the same check in our overlays: COOP_CAN.)"""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
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


@per_character
def m8b_growth(run, ch):
    """M8b criterion 5: Richter and Maria level up from EXP like Alucard (HP grows too)."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    level, hp = e.read(LEVEL), e.read(HP_MAX)
    e.write(EXP, 5000)
    run.step(30)
    run.expect(e.read(LEVEL) > level and e.read(HP_MAX) > hp, f"{NAMES[ch]} levels up",
               level=(level, e.read(LEVEL)), hp_max=(hp, e.read(HP_MAX)))


@per_character
def m8b_mist_step(run, ch):
    """M8b criterion 2: Richter and Maria pass the bars before the Lesser Demon with Form of Mist,
    and can't without it."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
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
            run.expect(min(xs) < 700, f"with Form of Mist, {NAMES[ch]} is past the bars", x=min(xs))
        else:
            run.expect(min(xs) > 760, "without it, the bars stop them", x=min(xs))


SPELLS_LEARNT, MP, MP_MAX = 0x80097B9C, 0x80097BB0, 0x80097BB4
SERVANT, FAM_ACTIVE_SWORD = 0x8006CBC4, 5  # g_Servant (include/game.h)


@scenario(start="entrance", disc=COOP_DISC)
def m8b_spell_shortcuts(run):
    """M8b criterion 6 (Alucard): with shortcuts on, a right-stick flick casts the spell the player
    put on that direction, if he knows it, for its MP. Not if he doesn't know it, nor with the
    shortcuts off. Each castable spell, on each direction."""
    from link.mailbox import SPELLS, spell_options
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    dirs = ("rs_up", "rs_right", "rs_down", "rs_left")

    def cast(spell, k, learnt=True, options=OPT_SHORTCUTS, servant=None):
        e.load_state(start)
        if servant is not None:
            e.write(SERVANT, servant)
        e.write(SPELLS_LEARNT, 0xFF if learnt else 0)
        e.write(MP, 99, "<i")
        e.write(MP_MAX, 99, "<i")
        spells = [None] * 4
        spells[k] = spell
        mb.set_options(options | spell_options(spells))
        run.step(10)
        run.step(1, dirs[k])
        for _ in range(200):
            run.step(1)
        return 99 - e.read(MP, "<i")

    castable = [i for i, name in enumerate(SPELLS) if name]
    for n, spell in enumerate(castable):
        sword = SPELLS[spell] == "Sword Brothers"
        if sword:  # only with the Sword familiar out (vanilla's rule)
            run.expect(cast(spell, n % 4) == 0, "Sword Brothers needs the Sword familiar out")
        used = cast(spell, n % 4, servant=FAM_ACTIVE_SWORD if sword else None)
        run.expect(used > 0, f"{SPELLS[spell]} casts with {dirs[n % 4]}", mp_used=used)
    run.expect(cast(castable[0], 0, learnt=False) == 0, "an unknown spell doesn't cast")
    run.expect(cast(castable[0], 0, options=0) == 0, "with the shortcuts off, the stick does nothing")


EQUIPMENT, ATTACK_HANDS, DEFENSE_EQUIP = 0x80097C00, 0x80097C1C, 0x80097C24
HP_NOW = STATUS + 0x23C
E_OFFHAND = 0x7E  # module/offhand.c
NO3, HALL_ROOM = 0x41, 72  # the castle entrance's zombie hall (room 14,40)
OFFHAND_ITEMS = ((19, "short sword"), (86, "sword"), (27, "two-handed sword"), (128, "club"),
                 (85, "fist"), (133, "throwing weapon"))
LEATHER_SHIELD, POTION, APPLE = 5, 159, 30


def offhand_entity(e):
    """(slot, attack) of the off-hand swing, or None."""
    for slot in range(0x18, 0x30):
        a = e.entity(slot)
        if e.read(a, "<H", 0x26) == E_OFFHAND:
            return slot, e.read(a, "<h", 0x40)
    return None


def enemies_hp(e):
    raw = e.read_bytes("g_Entities", 0xBC * 256)
    return {s: struct.unpack_from("<h", raw, s * 0xBC + 0x3E)[0] for s in range(64, 256)
            if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0]}


@per_character
def m8b_offhand(run, ch):
    """M8b criterion 7: one weapon of every class in the other hand hits with ○, with the game's
    own numbers for that hand (ATK + STR: g_Status.attackHands), drawn with its own sprite (the
    screenshots in the out folder). A shield adds its DEF, a potion and food heal."""
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    out = TOOLS["out"] / run.name
    start = e.save_state()
    for item, what in OFFHAND_ITEMS:
        e.load_state(start)
        e.write(EQUIPMENT, item)
        reload_as(run, mb, ch)
        mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)
        wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
            mb.self_presence()), 900, "arrived in the hall")
        run.step(90)  # the module loads the weapon
        attack, hit, shot = None, False, False
        for i in range(1200):
            route.heal(e)
            before = enemies_hp(e)
            pad = ("circle" if i % 24 == 0 else "") + ("+left" if (i // 120) % 2 else "+right")
            run.step(1, pad.strip("+"))
            sw = offhand_entity(e)
            if sw:
                attack = sw[1]
                if not shot and i % 24 == 6:
                    e.screenshot(out / f"{NAMES[ch].lower()}-{what.replace(' ', '-')}.png")
                    shot = True
                now = enemies_hp(e)
                if any(s in now and now[s] < hp < 32767 for s, hp in before.items()):
                    hit = True
                    break
        hands = e.read(ATTACK_HANDS, "<i")
        run.expect(attack is not None and attack == hands, f"{what}: swings with the hand's attack",
                   attack=attack, attack_hands=hands)
        run.expect(hit, f"{what}: hits an enemy")
    # A shield adds its DEF.
    e.load_state(start)
    reload_as(run, mb, ch)
    bare = e.read(DEFENSE_EQUIP, "<i")
    e.load_state(start)
    e.write(EQUIPMENT, LEATHER_SHIELD)
    reload_as(run, mb, ch)
    run.expect(e.read(DEFENSE_EQUIP, "<i") > bare, "a shield adds its DEF", bare=bare,
               shield=e.read(DEFENSE_EQUIP, "<i"))
    # A potion and food heal.
    for item, what in ((POTION, "a potion"), (APPLE, "food")):
        e.load_state(start)
        e.write(EQUIPMENT, item)
        reload_as(run, mb, ch)
        e.write(HP_NOW, 10, "<i")
        run.step(1, "circle")
        run.step(120)
        run.expect(e.read(HP_NOW, "<i") > 10, f"{what} heals", hp=e.read(HP_NOW, "<i"))


SERVANT_LOADED = 0x80073064  # g_ServantLoaded
HOLY_SYMBOL, BAT_CARD, GHOST_CARD = 14, 18, 19
POISON_WATER = 0x8009744C  # g_unkGraphicsStruct.D_8009744C: the stage marks the player in poison water


@per_character
def m8b_familiar(run, ch):
    """M8b §3: the familiar cards work for Richter and Maria too. With a card on, the module loads
    the familiar after a load (their code runs from the expansion RAM, so it fits), it comes out,
    and they still play."""
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    for relic, fam in ((BAT_CARD, 1), (GHOST_CARD, 2)):
        e.load_state(start)
        e.write(STATUS, RELIC_ON, "<B", relic)
        reload_as(run, mb, ch)
        run.step(300)
        ids = [e.read(e.entity(s), "<H", 0x26) for s in range(4, 64)]
        run.expect(e.read(SERVANT) == fam and e.read(SERVANT_LOADED) == fam,
                   f"card {relic}: the familiar is loaded", servant=e.read(SERVANT),
                   loaded=e.read(SERVANT_LOADED))
        run.expect(any(0xD0 <= i < 0xE0 for i in ids), f"card {relic}: the familiar is out")
        s0 = e.snapshot()
        s = run.play(walker("left", attack_every=12), 300)
        run.expect(s["hp"] > 0 and (s["world_x"] != s0["world_x"] or s["room"] != s0["room"]),
                   f"card {relic}: {NAMES[ch]} still plays")


@per_character
def m8b_poison_water(run, ch):
    """M8b §2: poison water hurts Richter and Maria without Holy Symbol, as it does Alucard, and
    not with it."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    start = e.save_state()
    for symbol in (False, True):
        e.load_state(start)
        if symbol:
            e.write(STATUS, RELIC_ON, "<B", HOLY_SYMBOL)
        hp = e.read(HP_NOW, "<i")
        for _ in range(180):
            e.write(POISON_WATER, 8, "<i")
            run.step(1)
        lost = hp - e.read(HP_NOW, "<i")
        if symbol:
            run.expect(lost == 0, "with Holy Symbol, poison water doesn't hurt", lost=lost)
        else:
            run.expect(lost > 0, "without it, poison water hurts", lost=lost)


SKILL_OF_WOLF = 6
HEARTS, SUBWEAPON = 0x80097BA8, 0x80097BFC  # g_Status (include/game.h)


def travel(run, inputs):
    """How far (px) the player gets along x while the inputs play, then settles."""
    e = run.emu
    x0, best = e.snapshot()["world_x"], 0
    for b in inputs:
        run.step(1, b)
        best = max(best, abs(e.snapshot()["world_x"] - x0))
    run.step(30)
    return best


@per_character
def m8b_more_gates(run, ch):
    """M8b criterion 1 (the other rows of §3): each move needs its relic, for Richter and Maria.
    The second jump (Leap Stone), climbing (Soul of Bat, with the Leap Stone), the slide (Soul of
    Wolf), item / guardian crashes (Echo of Bat: hearts spent on △), the blade dash (Skill of
    Wolf, on R2 with the shortcuts on)."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    mb.set_options(OPT_SHORTCUTS)
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)  # room to jump: the zombie hall
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    run.step(90)
    start = e.save_state()

    def measure(relics, how):
        e.load_state(start)
        for r in relics:
            e.write(STATUS, RELIC_ON, "<B", r)
        return how()

    if ch == CHAR_RICHTER:  # his backflip: jump again right after leaving the ground; Soul of Bat: again near its top
        second = ["cross"] * 2 + [""] * 2 + ["cross"] * 2 + [""] * 60
        climb = (["cross"] * 2 + [""] * 2) * 40 + [""] * 60
    else:  # her double jump: a full jump, then again at the top; Soul of Bat: again and again
        second = ["cross"] * 16 + [""] * 2 + ["cross"] * 12 + [""] * 60
        climb = (["cross"] * 12 + [""] * 2) * 8 + [""] * 60
    slide = ["down"] * 4 + ["down+cross"] * 3 + ["down"] * 30
    dash = ["r2"] * 2 + [""] * 40

    def crash():
        e.write(SUBWEAPON, 1)
        e.write(HEARTS, 50, "<i")
        run.step(1, "triangle")
        run.step(90)
        return 50 - e.read(HEARTS, "<i")

    rows = [("the second jump", [], [LEAP_STONE],
             (lambda: travel(run, second)) if ch == CHAR_RICHTER else (lambda: rise(run, second)), 12),
            ("climbing", [LEAP_STONE], [LEAP_STONE, SOUL_OF_BAT], lambda: rise(run, climb), 24),
            ("the slide", [], [SOUL_OF_WOLF], lambda: travel(run, slide), 24),
            ("crashes", [], [ECHO_OF_BAT], crash, 1),
            ("the blade dash (R2)", [], [SKILL_OF_WOLF], lambda: travel(run, dash), 24)]
    got = [(what, measure(base, how), measure(more, how), margin) for what, base, more, how, margin in rows]
    for what, without, with_, margin in got:
        run.expect(with_ >= without + margin, f"{what} needs its relic", without=without, with_relic=with_,
                   all=[g[:3] for g in got])
