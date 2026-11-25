"""M8 and M8b scenarios (design/M8-maria-and-richter.md, design/M8b-character-balance.md): one
game on the co-op disc, playing as Richter or Maria in Alucard's castle. Each character test is
registered once per character: <name>_richter, <name>_maria (Maria needs the dev DXC disc)."""

import struct

from bots import walker
from coop_env import REPO
from emu import SYMBOLS
from link.adapter import HarnessAdapter
from link.mailbox import (BUSY, CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CHAR_SAT_MARIA, CHAR_ULT_MARIA, CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW,
                          CHAR_BLOB_ADDR, IN_PLAY, OPT_SHORTCUTS, RULE_NO_GEAR_EFFECTS, Mailbox)
from module import COOP_DISC, maria_blob, symbols
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
    if character in (CHAR_MARIA, CHAR_ULT_MARIA, CHAR_SAT_MARIA, 5):  # 5: Ultimate Richter
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


def per_character(fn=None, only=None):
    """Registers fn(run, character) as <name>_richter and <name>_maria (only="richter": just that one)."""
    if fn is None:
        return lambda f: per_character(f, only)
    for ch, name in NAMES.items():
        if only and name.lower() != only:
            continue
        def one(run, ch=ch):
            return fn(run, ch)
        one.__name__ = f"{fn.__name__}_{name.lower()}"
        one.__doc__ = fn.__doc__
        scenario(start="entrance", disc=COOP_DISC)(one)
    return fn


@per_character
def in_the_castle(run, ch):
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
def relic_gates(run, ch):
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


STATS_BASE, STATS_TOTAL = 0x80097BB8, 0x80097BD8  # g_Status.statsBase[4], statsTotal[4]: STR, CON, INT, LCK


@per_character
def level_up_stats(run, ch):
    """Issue 171: Maria's status page didn't change when she levelled up. Her stats grow with her
    level, and so do the totals the status page shows."""
    import struct
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    base, total = (struct.unpack("<4i", e.read_bytes(a, 16)) for a in (STATS_BASE, STATS_TOTAL))
    e.write(EXP, 5000)
    run.step(30)
    base2, total2 = (struct.unpack("<4i", e.read_bytes(a, 16)) for a in (STATS_BASE, STATS_TOTAL))
    run.expect(all(b2 >= b for b, b2 in zip(base, base2)) and base2 != base, "her stats grow", was=base, now=base2)
    run.expect(all(t2 - t == b2 - b for t, t2, b, b2 in zip(total, total2, base, base2)),
               "and the totals (the status page's) by as much", was=total, now=total2)


@per_character
def hit_shows_its_number(run, ch):
    """Issue 171: a hit on Richter or Maria showed no number, as it does over Alucard. The HP it took
    rises from them (DRA's number entity, run by their own entity loop)."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    run.step(60)
    hp = e.read(HP_NOW, "<i")
    e.write("g_Entities", 12, "<h", 0x3E)  # PLAYER.hitPoints, as hit detection leaves them
    e.write("g_Entities", 1, "<H", 0x44)   # PLAYER.hitParams: a plain hit
    seen = []
    for k in range(20):
        run.step(1)
        if k == 8:  # evidence: the number over them
            from coop_env import TOOLS
            (TOOLS["out"] / run.name).mkdir(parents=True, exist_ok=True)
            x, y = e.read("g_Entities", "<h", 2), e.read("g_Entities", "<h", 6)
            e.screenshot().crop((x - 48, y - 64, x + 48, y + 24)).resize((384, 352)).save(TOOLS["out"] / run.name / "number.png")
        for slot in range(0x38, 0x40):
            if e.read(e.entity(slot), "<H", 0x26) == 0xCF:
                seen.append((slot, e.read(e.entity(slot), "<H", 0x2C), e.read(e.entity(slot), "<h", 0x80)))
    lost = hp - e.read(HP_NOW, "<i")
    run.expect(lost > 0, "the hit hurts", lost=lost)
    run.expect(seen and max(st for _, st, _ in seen) > 0, "its number comes out, and runs", seen=seen[:3])
    run.expect(seen and seen[0][2] == lost, "showing the HP it took", number=seen[0][2] if seen else None, lost=lost)


# Mist grates to step through: (where to arrive, the way in, the grate's x span). The Lesser Demon's
# bars (mist_step), and the Long Library's lower grate from issue 211's report (room 0, y 936).
GRATES = (((LIB, 0, 1100, 700), "left", (700, 760)), ((LIB, 0, 700, 936), "right", (762, 900)))
JUMPS = ((8, 30), (20, 45), (26, 50), (30, 70), (12, 33))  # jumps into the grate: ✕ held h of every n frames
# What the player pressed at the lower grate in the last 500 frames before issue 211's report
# (pad, frames): jumping and dashing into it, then trying to walk back.
REPORT_211 = (("", 1), ("right", 14), ("cross+right", 6), ("right", 45), ("cross+right", 21), ("cross+right+square", 11),
              ("cross+right", 3), ("right", 19), ("", 8), ("left", 9), ("", 1), ("cross+up", 1), ("cross+right", 8),
              ("right", 55), ("right+square", 12), ("right", 19), ("right+square", 7), ("right", 18), ("", 16),
              ("cross", 3), ("cross+right", 21), ("cross+l1+r1+right", 14), ("cross+right", 2), ("right", 16),
              ("cross+right", 26), ("cross+r1+right", 13), ("cross+right", 10), ("right", 25), ("cross+right", 25),
              ("right", 32), ("", 15), ("cross", 9), ("cross+left", 12), ("cross+l1+left", 3))


@per_character
def mist_step_never_stuck(run, ch):
    """Issue 211: Maria got stuck at a grate: unseen and deaf to the pad, for what looked like for
    good. Every way into a grate: they always end on one side of it, able to walk away soon after."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    e.write(STATUS, RELIC_ON, "<B", FORM_OF_MIST)
    x = lambda: mb.self_presence().x
    for spot, way, span in GRATES:
        mb.command(CMD_ARRIVE, *spot)
        wait(run, lambda: (lambda p: p.stage == LIB and p.flags & IN_PLAY and not p.flags & BUSY)(
            mb.self_presence()), 900, "arrived in the Long Library")
        run.step(60)
        start = e.save_state()
        back = "right" if way == "left" else "left"

        def into(i, how):  # the inputs at frame i of going in
            return {"walk": way, "dash": f"{way}+r1" if i % 20 < 4 else way,
                    "dash_only": "r1" if i % 20 < 4 else "", "jump": f"{way}+cross" if i % 40 < 15 else way,
                    "attack": f"{way}+square" if i % 10 < 3 else way, "crouch": f"{way}+down" if i > 25 else way,
                    "mash": (way, f"{way}+l1", f"{way}+r1", f"{way}+square", f"{way}+cross", f"{way}+l1+r1")[i % 6],
                    "back_off": way if i < 38 else back,
                    **{f"jump_{h}_{n}": f"{way}+cross" if i % n < h else way for h, n in JUMPS}}[how]

        hows = ("walk", "dash", "dash_only", "jump", "attack", "crouch", "mash", "back_off") + tuple(
            f"jump_{h}_{n}" for h, n in JUMPS)
        for how in hows + (("report",) if way == "right" else ()):
            e.load_state(start)
            xs = []
            pads = ([way] * 120 + [p for p, n in REPORT_211 for _ in range(n)] if how == "report"
                    else [into(i, how) for i in range(400)])
            for pad in pads:
                route.heal(e)
                run.step(1, pad)
                xs.append(x())
            run.step(60)
            end, after = x(), e.save_state()
            moved = 0
            for go in ("left", "right"):  # (one way may be a wall)
                e.load_state(after)
                run.step(90, go)
                moved = max(moved, abs(x() - end))
            what = f"{way} at y {spot[3]}, {how}"
            run.expect(not span[0] <= end <= span[1], f"{what}: not left inside the grate", x=end, xs=xs[::40])
            run.expect(moved > 16, f"{what}: can walk away soon after", x=end, moved=moved, xs=xs[::40])


SPELLS_LEARNT, MP, MP_MAX = 0x80097B9C, 0x80097BB0, 0x80097BB4
SERVANT, FAM_ACTIVE_SWORD = 0x8006CBC4, 5  # g_Servant (include/game.h)


EQUIPMENT, ATTACK_HANDS, DEFENSE_EQUIP = 0x80097C00, 0x80097C1C, 0x80097C24
HP_NOW = STATUS + 0x23C
NO3, HALL_ROOM = 0x41, 72  # the castle entrance's zombie hall (room 14,40)
OFFHAND_ITEMS = ((19, "short sword"), (86, "sword"), (27, "two-handed sword"), (128, "club"),
                 (85, "fist"), (133, "throwing weapon"))
LEATHER_SHIELD, POTION, APPLE = 5, 159, 30
ATTACK_NOW = 0x80072F66  # g_Player.unk46: an attack of the player's own is under way


def enemies_hp(e):
    raw = e.read_bytes("g_Entities", 0xBC * 256)
    return {s: struct.unpack_from("<h", raw, s * 0xBC + 0x3E)[0] for s in range(64, 256)
            if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0]}


MENU_STR, ALUCARD_NAME = 0x800A8258, bytes.fromhex("212C3523213224FF")  # g_MenuStr; [0] is the status page's name


WEAPON_SELF, WEAPON_CLUT_OFS = 0x80710000, 0x7020  # module/link.h: CoopWeapon
WEAPON_PRG, FRAMES_OFS, PAL_SIZE = 0x8017A000, 0x40, 0x20
OFFHAND_PALS, BANK_PAL_Y = 0x2D0, 0x1F0  # module/offhand.c


SERVANT_LOADED = 0x80073064  # g_ServantLoaded
HOLY_SYMBOL, BAT_CARD, GHOST_CARD = 14, 18, 19
FAERIE_CARD, DEMON_CARD, SWORD_CARD = 0x14, 0x15, 0x16


POTION, HEALING_MAIL, ARMOR = 0x9F, 0x11, 0x80097C0C  # ITEM_POTION, ITEM_HEALING_MAIL; g_Status.equipment[ARMOR_SLOT]
HAND_COUNT = STATUS + 0x26  # g_Status.equipHandCount
HP_MAX = STATUS + 0x240


@per_character
def familiar_faerie_potion(run, ch):
    """Issue 200 (0.16.3): the faerie gave Richter potion after potion and none healed him: her potion
    sets g_Player.healKind, which only Alucard's code took. At a tenth of his HP, she uses one and
    it heals."""
    e, mb = run.emu, mailbox(run)
    e.write(STATUS, RELIC_ON, "<B", FAERIE_CARD)
    reload_as(run, mb, ch)
    run.step(300)
    e.write(HAND_COUNT + POTION, 5, "<B")
    hp_max = e.read(HP_MAX, "<i")
    low = max(1, hp_max // 10)
    e.write(HP_NOW, low, "<i")
    healed = None
    for t in range(2400):
        run.step(1)
        if e.read(HP_NOW, "<i") > low:
            healed = t
            break
    run.expect(e.read(HAND_COUNT + POTION, "<B") < 5, "the faerie uses a potion", potions=e.read(HAND_COUNT + POTION, "<B"))
    run.expect(healed is not None, "it heals", hp=e.read(HP_NOW, "<i"), low=low, hp_max=hp_max)


@per_character(only="maria")
def healing_mail(run, ch):
    """Issue 202 (0.16.3): Healing Mail did nothing for Richter and Maria. Walking in it heals 1 HP
    every 128 frames, as it does Alucard; standing doesn't."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    e.write(ARMOR, HEALING_MAIL, "<I")
    half = e.read(HP_MAX, "<i") // 2
    e.write(HP_NOW, half, "<i")
    run.step(600)
    run.expect(e.read(HP_NOW, "<i") == half, "standing: no healing", hp=e.read(HP_NOW, "<i"), was=half)
    for i in range(8):  # short legs: the timer starts over whenever they stop, as Alucard's does
        run.play(walker("left" if i % 2 else "right"), 75)
    run.expect(e.read(HP_NOW, "<i") >= half + 3, "walking: 1 HP every 128 frames", hp=e.read(HP_NOW, "<i"), was=half)
    mb.set_rules(off=RULE_NO_GEAR_EFFECTS)  # the castle's rule off: no healing
    e.write(HP_NOW, half, "<i")
    for i in range(8):
        run.play(walker("left" if i % 2 else "right"), 75)
    run.expect(e.read(HP_NOW, "<i") == half, "with gear effects off, walking doesn't heal", hp=e.read(HP_NOW, "<i"))


LIBRARY_CARD, BLOOD_CLOAK, CAPE, LIB = 0xA6, 0x36, 0x80097C10, 0x02  # items; equipment[CAPE_SLOT]; the Library
HEARTS = HP_NOW + 8  # g_Status.hearts


@per_character
def library_card(run, ch):
    """Issue 197 (0.16.3, 0.17.0): Richter and Maria couldn't use the Library Card. In a hand, ○
    takes them to the Library, and the card is used up."""
    e, mb = run.emu, mailbox(run)
    e.write(EQUIPMENT + 4, LIBRARY_CARD)
    reload_as(run, mb, ch)
    run.step(60)
    run.step(1, "circle")
    for _ in range(1200):
        run.step(1)
        if e.read("g_StageId") == LIB and mb.self_presence().flags & IN_PLAY:
            break
    run.expect(e.read("g_StageId") == LIB, "they're in the Library", stage=e.read("g_StageId"))
    run.expect(e.read(EQUIPMENT) != LIBRARY_CARD, "the card is used up", hand=e.read(EQUIPMENT))


@per_character(only="maria")
def blood_cloak(run, ch):
    """Issue 202 (0.16.3): Blood Cloak gave Richter and Maria no hearts when hit (Alucard's
    HandleDamage does it; their hits don't go through it). A hit gives as many hearts as it took."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    got = {}
    for cloak in (False, True):
        e.write(CAPE, BLOOD_CLOAK if cloak else 0, "<I")
        run.step(120)
        e.write(HEARTS, 0, "<i")
        hp = e.read(HP_NOW, "<i")
        e.write("g_Entities", 20, "<h", 0x3E)  # PLAYER.hitPoints, as hit detection leaves them
        e.write("g_Entities", 1, "<H", 0x44)   # PLAYER.hitParams: a plain hit
        run.step(4)
        lost, hearts = hp - e.read(HP_NOW, "<i"), e.read(HEARTS, "<i")
        run.expect(lost > 0, f"{'with' if cloak else 'without'} the cloak, the hit hurts", lost=lost)
        got[cloak] = (hearts, lost)
        run.step(120)
    # (Maria's own code gives a few hearts for a hit too: the cloak's come on top)
    run.expect(got[True][0] - got[False][0] == got[True][1], "with it, as many more hearts as the hit took", got=got)
    mb.set_rules(off=RULE_NO_GEAR_EFFECTS)  # the castle's rule off: the cloak gives nothing
    e.write(HEARTS, 0, "<i")
    e.write("g_Entities", 20, "<h", 0x3E)
    e.write("g_Entities", 1, "<H", 0x44)
    run.step(4)
    run.expect(e.read(HEARTS, "<i") == got[False][0], "with gear effects off, no more hearts than without it",
               hearts=e.read(HEARTS, "<i"), without=got[False][0])


# Gear that changes a hit or a sub-weapon in Alucard's code (src/dra/5D5BC.c), for Richter and Maria (#202)
HEAD, ACC1, ACC2 = 0x80097C08, 0x80097C14, 0x80097C18  # g_Status.equipment[HEAD..ACCESSORY_2]
LCK_BASE = 0x80097BB8 + 12                             # g_Status.statsBase[STAT_LCK]
STAT_BUFFS = 0x80139828                                # g_StatBuffTimers ([0]: DEF)
BRILLIANT_MAIL, FURY_PLATE, BALLROOM_MASK, RUBY_CIRCLET, CAT_EYE = 0x14, 0x16, 0x1C, 0x27, 0x2B  # include/items.h
STAUROLITE, HEART_BROACH, TALISMAN = 0x3D, 0x4D, 0x53
FIRE, SOLID_FROM_BELOW = 0x8000, 0x80                  # ELEMENT_FIRE, EFFECT_SOLID_FROM_BELOW


def hit(run, params, points=0x3E):
    """A hit as hit detection leaves it on the player; returns the HP it took (negative: healed)."""
    e = run.emu
    hp = e.read(HP_NOW, "<i")
    e.write("g_Entities", points, "<h", 0x3E)  # PLAYER.hitPoints
    e.write("g_Entities", params, "<H", 0x44)  # PLAYER.hitParams: effects | damage kind
    run.step(4)
    taken = hp - e.read(HP_NOW, "<i")
    run.step(90)  # out of the hit, and its invincibility
    e.write(HP_NOW, hp, "<i")
    return taken


@per_character
def gear_on_hits(run, ch):
    """Issue 202: gear that changes a hit for Alucard does it for Richter and Maria too. A fire hit
    heals with the Ruby Circlet (it absorbs fire), a kind-7 hit heals twice over with the Cat-Eye
    Circlet, the Ballroom Mask takes a fifth off, two Talismans with high luck dodge every hit, and
    the Fury Plate raises DEF after one. With the castle's gear effects off, only the absorbing
    (an element, as resistances are) is left."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    e.write(HP_NOW, e.read(HP_MAX, "<i") // 2, "<i")
    run.step(30)
    start = e.save_state()

    def wearing(slots, params, rules_off=0, points=0x3E):
        e.load_state(start)
        if rules_off:
            mb.set_rules(off=rules_off)
        for addr, item in slots:
            e.write(addr, item, "<I")
        run.step(30)
        return hit(run, params, points)

    plain = wearing([], 4)
    run.expect(plain > 0, "a plain hit hurts", taken=plain)
    fire = wearing([(HEAD, RUBY_CIRCLET)], FIRE | 4)
    run.expect(fire < 0, "the Ruby Circlet: a fire hit heals", taken=fire)
    cat = wearing([(HEAD, CAT_EYE)], 7)
    room = e.read(HP_MAX, "<i") - e.read(HP_MAX, "<i") // 2
    run.expect(-cat == min(2 * 0x3E, room), "the Cat-Eye Circlet: a kind-7 hit heals twice its points (up to max HP)",
               taken=cat, room=room)
    bare = wearing([], SOLID_FROM_BELOW | 4, points=30) + e.read(DEFENSE_EQUIP, "<i")
    masked = wearing([(HEAD, BALLROOM_MASK)], SOLID_FROM_BELOW | 4, points=30) + e.read(DEFENSE_EQUIP, "<i")
    run.expect(bare - masked == 30 // 5, "the Ballroom Mask takes a fifth off (before defense)", bare=bare, masked=masked)
    e.load_state(start)
    e.write(LCK_BASE, 400, "<i")
    start_lucky = e.save_state()
    e.load_state(start_lucky)
    e.write(ACC1, TALISMAN, "<I")
    e.write(ACC2, TALISMAN, "<I")
    run.step(30)
    dodged = [hit(run, 4) for _ in range(5)]
    run.expect(dodged == [0] * 5, "two Talismans and 400 luck: every hit is dodged", taken=dodged)
    e.load_state(start)
    e.write(0x80097C0C, FURY_PLATE, "<I")
    run.step(30)
    e.write(STAT_BUFFS, 0, "<i")
    hit(run, 4)
    run.expect(e.read(STAT_BUFFS, "<i") > 0x100, "the Fury Plate: DEF up after a hit", timer=e.read(STAT_BUFFS, "<i"))
    mask_off = wearing([(HEAD, BALLROOM_MASK)], SOLID_FROM_BELOW | 4, RULE_NO_GEAR_EFFECTS, points=30) + \
        e.read(DEFENSE_EQUIP, "<i")
    fire_off = wearing([(HEAD, RUBY_CIRCLET)], FIRE | 4, RULE_NO_GEAR_EFFECTS)
    run.expect(mask_off == bare and fire_off < 0, "gear effects off: no mask, the circlet still absorbs",
               mask_off=mask_off, bare=bare, fire_off=fire_off)


def throw(run, subweapon, frames=60):
    """Throws a sub-weapon (↑ + □); returns (hearts spent, the highest attack among the player's
    sub-weapon entities meanwhile)."""
    e = run.emu
    e.write(SUBWEAPON, subweapon)
    e.write(HEARTS, 50, "<i")
    run.step(2, "up+square")
    top = 0
    for _ in range(frames):
        run.step(1)
        for slot in range(4, 64):
            if e.read("g_Entities", "<H", slot * 0xBC + 0x26):  # entityId
                top = max(top, e.read("g_Entities", "<h", slot * 0xBC + 0x40))  # attack
    return 50 - e.read(HEARTS, "<i"), top


@per_character
def gear_on_subweapons(run, ch):
    """Issue 202: a Heart Broach halves what a sub-weapon (Maria's guardian) costs, Brilliant Mail
    adds 10 to its attack, and for Richter a Staurolite doubles holy water's, as they do
    Alucard's. With the castle's gear effects off, none of them."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    run.step(30)
    start = e.save_state()

    def with_gear(slots, sub, rules_off=0):
        e.load_state(start)
        if rules_off:
            mb.set_rules(off=rules_off)
        for addr, item in slots:
            e.write(addr, item, "<I")
        run.step(30)
        return throw(run, sub)

    for first in range(1, 10):  # one that costs 2 or more, so halving shows (the dagger costs 1)
        cost, attack = with_gear([], first)
        if cost >= 2:
            break
    run.expect(cost >= 2 and attack > 0, "a sub-weapon costs hearts and hits", cost=cost, attack=attack, sub=first)
    broach, _ = with_gear([(ACC1, HEART_BROACH)], first)
    run.expect(broach == max(1, cost // 2), "a Heart Broach halves the cost", cost=cost, broach=broach)
    _, mail = with_gear([(0x80097C0C, BRILLIANT_MAIL)], first)
    run.expect(mail >= attack + 10, "Brilliant Mail: 10 more on the sub-weapon's attack", attack=attack, mail=mail)
    off = with_gear([(ACC1, HEART_BROACH), (0x80097C0C, BRILLIANT_MAIL)], first, rules_off=RULE_NO_GEAR_EFFECTS)
    run.expect(off == (cost, attack), "gear effects off: neither", off=off, plain=(cost, attack))
    if ch == CHAR_RICHTER:
        holy = 3  # SUBWPN_HOLY_WATER (characters/richter-ps1/coop_ric.c)
        _, water = with_gear([], holy)
        _, stauro = with_gear([(ACC1, STAUROLITE)], holy)
        run.expect(water > 0 and stauro >= 2 * water - 2, "a Staurolite doubles holy water's attack", water=water, stauro=stauro)


STATS_BASE, STATS_TOTAL = 0x80097BB8, 0x80097BD8  # g_Status.statsBase / statsTotal: STR, CON, INT, LCK
STR, INT = 0, 2
GAS_CLOUD_RELIC = 9  # RELIC_GAS_CLOUD


@scenario(start="entrance", disc=COOP_DISC)
def maria_attack_scaling(run):
    """Issue 238 (Tucker: STR for her kicks, INT for her guardians). Under "Alucard's stats", her
    guardians' attack grows with INT and not STR; her slide kick's with STR and not INT. The turtle's
    crash poisons with Gas Cloud (it was never told it was the turtle's)."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_MARIA)
    for r in (SOUL_OF_WOLF, GAS_CLOUD_RELIC):
        e.write(STATUS + r, RELIC_ON, "<B")
    run.step(30)
    start = e.save_state()

    def top_attack(stat, add, inputs, sub=None):
        e.load_state(start)
        if stat is not None:
            for base in (STATS_BASE, STATS_TOTAL):
                e.write(base + 4 * stat, e.read(base + 4 * stat, "<i") + add, "<i")
        if sub is not None:
            e.write(SUBWEAPON, sub)
            e.write(HEARTS, 50, "<i")
        top, poison, seen = 0, False, set()
        for b in inputs:
            run.step(1, b)
            for slot in range(4, 64):
                if e.read("g_Entities", "<H", slot * 0xBC + 0x26):
                    attack, element = e.read("g_Entities", "<h", slot * 0xBC + 0x40), e.read("g_Entities", "<H", slot * 0xBC + 0x42)
                    top = max(top, attack)
                    poison |= bool(attack and element & 0x80)  # attackElement: ELEMENT_POISON
                    seen.add((e.read("g_Entities", "<H", slot * 0xBC + 0x26), attack, element))
        top_attack.seen = (sorted(seen)[:12], 50 - e.read(HEARTS, "<i"))
        return top, poison

    guardian = ["up+square"] * 2 + [""] * 60
    kick = ["right"] * 20 + ["right+down"] * 4 + ["right+down+cross"] * 3 + ["down"] * 30
    g = {k: top_attack(st, 100, guardian, 1)[0] for k, st in (("plain", None), ("str", STR), ("int", INT))}
    run.expect(g["plain"] > 0 and g["int"] > g["plain"] and g["str"] == g["plain"],
               "a guardian (Cardinal) grows with INT, not STR", attack=g)
    k = {k: top_attack(st, 100, kick)[0] for k, st in (("plain", None), ("str", STR), ("int", INT))}
    run.expect(k["plain"] > 0 and k["str"] > k["plain"] and k["int"] == k["plain"],
               "her slide kick grows with STR, not INT", attack=k)
    e.load_state(start)
    e.write(STATUS + ECHO_OF_BAT, RELIC_ON, "<B")  # crashes, done where relic_gates_more does them
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    run.step(90)
    start = e.save_state()
    _, poison = top_attack(None, 0, ["triangle"] + [""] * 150, 3)
    run.expect(poison, "with Gas Cloud, the turtle's crash poisons", seen=top_attack.seen[0])


ELEMENT_POISON, ELEMENTS_IMMUNE = 0x80, 0x80097C2C
HIT_POINTS, HIT_PARAMS, ENTITY_PALETTE = 0x3E, 0x44, 0x16


PLAYER_HUD_PRIM, PRIM_BUF, PRIM_SIZE, PRIM_TPAGE, ALUCARD_HUD_TPAGE = 0x80137970, 0x80086FEC, 0x34, 0x1A, 0x1F
SHORT_SWORD = 19
ALUCARD_RATE = 30  # damage_rate_alucard, measured


def damage_a_second(run, e, mb, ch, seconds=10, hand=None):
    """Issue 114: mashing the plain attack at an enemy held on it, in the hall: swing rate,
    hitboxes and the target's invincibility, all counted the same way. Returns (damage a second,
    the most in one hit)."""
    from scenarios_m12 import pin_target
    if hand is None:
        hand = 1 if ch else 0  # Richter's, Maria's: the second hand, so □ is their own
    e.write(EQUIPMENT + 4 * hand, SHORT_SWORD)
    reload_as(run, mb, ch)
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    run.step(90)
    target = min(s for s, hp in enemies_hp(e).items() if 0 < hp < 32767)
    enemy, full = e.entity(target), 20000
    start = e.save_state()
    best, top = 0, 0
    for every in (8, 12, 16, 20, 24, 32):  # however fast this character can usefully press
        e.load_state(start)
        total = 0
        for i in range(seconds * 60):
            route.heal(e)
            x = e.read(e.entity(0), "<i") + (-1 if e.read(e.entity(0) + 0x14, "<H") else 1) * (14 << 16)
            e.write(enemy, x, "<i")
            e.write(enemy + 4, e.read(e.entity(0) + 4, "<i"), "<i")
            e.write(enemy + 0x3E, full, "<h")
            e.write(enemy + 0x40, 0, "<h")  # its own attack
            pin_target(e)  # a sword stabs higher than this room's enemies stand
            run.step(1, "square" if i % every < 2 else "")
            lost = full - e.read(enemy + 0x3E, "<h")
            total += lost
            top = max(top, lost)
        best = max(best, total / seconds)
    return best, top


@per_character(only="richter")
def damage_rate(run, ch):
    """Issue 114: what this character does a second."""
    e, mb = run.emu, mailbox(run)
    rate, top = damage_a_second(run, e, mb, ch)
    run.expect(ALUCARD_RATE * 0.7 < rate < ALUCARD_RATE * 1.3,
               f"{rate:.0f} damage a second, {top} a hit: near Alucard's {ALUCARD_RATE}")


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


NO1, TELESCOPE_ROOM, TELESCOPE_X, TELESCOPE_Y = 0x01, 24, 339, 160  # the Outer Wall's foot (layout: E_ID_28)


STR_TOTAL = 0x80097BD8  # g_Status.statsTotal[STAT_STR]


@scenario(start="entrance", disc=COOP_DISC)
def richter_backflips_turn(run):
    """#198 and #199: with Soul of Bat, Richter's chained backflips go the way the player holds,
    so he climbs toward a ledge on either side (the Gravity Boots' way in). From a standing jump
    and its backflip, more backflips holding right take him up and right, and holding left up and
    left, from either facing; with nothing held, each goes backwards, as ever."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_RICHTER)
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 700, 200)  # room to jump: the zombie hall
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    run.step(90)
    for r in (LEAP_STONE, SOUL_OF_BAT):
        e.write(STATUS, RELIC_ON, "<B", r)
    start = e.save_state()
    got = {}
    for facing in ("left", "right"):
        for held in ("left", "right", ""):
            e.load_state(start)
            run.step(2, facing)
            run.step(10)
            x0, y0 = e.snapshot()["world_x"], e.snapshot()["world_y"]
            top = 0
            for i in range(30):  # a standing jump and its backflip, then again near the top of each
                hold = held if i >= 2 else ""
                run.step(2, "+".join(p for p in (hold, "cross") if p))
                run.step(2, hold)
                top = max(top, y0 - e.snapshot()["world_y"])
            got[f"{facing}/{held or '-'}"] = (e.snapshot()["world_x"] - x0, top)
            run.step(60)
    for key, (dx, top) in got.items():
        facing, held = key.split("/")
        if held == "-":
            held, what = ("right" if facing == "left" else "left"), "nothing held: backwards, as ever"
        else:
            what = f"holding {held}: the backflips take him {held}"
        run.expect(top > 80 and (dx > 48 if held == "right" else dx < -48), f"facing {facing}, {what}, and up",
                   dx=dx, rise=top, all=got)


SHURIKEN = 133  # a thrown weapon (OFFHAND_ITEMS)


@per_character
def status_attack(run, ch):
    """#204: the status page's ATK. Beside □ it's their own attack (the whip's, the owl's: 20% or
    50% of it, plus STR) while the first hand holds nothing □ uses, else that hand's (a weapon in
    it is what □ swings); beside ○, the second hand's."""
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    own = 32 * 20 // 100 if ch == CHAR_RICHTER else 12 * 50 // 100  # coop_attack.h

    def hands(first, second=0):
        e.load_state(start)
        e.write(EQUIPMENT, first)
        e.write(EQUIPMENT + 4, second)
        reload_as(run, mb, ch)
        return e.read(ATTACK_HANDS, "<i"), e.read(ATTACK_HANDS + 4, "<i"), e.read(STR_TOTAL, "<i")

    square, circle, strength = hands(0)
    run.expect(square == own + strength, "empty hands: □ shows their own attack", square=square, str=strength)
    run.expect(circle == 0, "...and ○ shows nothing", circle=circle)
    s, c, _ = hands(LEATHER_SHIELD)
    run.expect(s < square, "a shield in the first hand: □ guards (#214), so it shows the shield's attack, not theirs",
               square=s, own=square)
    for item, what in ((OFFHAND_ITEMS[0][0], "a short sword"), (SHURIKEN, "a thrown weapon")):
        s, c, _ = hands(0, item)
        run.expect(s == square, f"{what} in the second hand: □ stays their own attack", square=s)
        run.expect(c > 0, f"...and ○ shows its attack", circle=c)
        s, c, _ = hands(item)
        run.expect(s > 0 and s != square, f"{what} in the first hand: □ shows its attack", square=s)
        run.expect(c == 0, "...and ○ nothing", circle=c)


def weapon_ids(e):
    """The weapon overlays' entities in slots 4-63: their ids (0xE0+: the first hand's, 0xF0+: the second's)."""
    import struct
    raw = e.read_bytes("g_Entities", 0xBC * 64)
    return {struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0] for s in range(4, 64)} & set(range(0xE0, 0x100))


SHEET_COPIES = 0x80700000  # module/coop_api.h WEAPON_SHEET_ADDR: each hand's sheet (16 KB), kept in the 8MB


@per_character
def hands_like_alucard(run, ch):
    """As Alucard's: □ uses the first hand and ○ the second. With nothing in the first hand □ is
    their own attack (the whip, the owl); with a weapon there □ swings it and ↑+□ still throws the
    subweapon; a two-handed weapon is both buttons. Each swing draws from its own hand's sheet (one
    sheet's room in VRAM: the swinging hand's goes in)."""
    from scenarios_m12 import AXE, SUBWEAPON, HEARTS as HEARTS_NOW
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    sword, club, two_handed = OFFHAND_ITEMS[0][0], OFFHAND_ITEMS[3][0], OFFHAND_ITEMS[2][0]

    def holding(first, second):
        e.load_state(start)
        e.write(EQUIPMENT, first)
        e.write(EQUIPMENT + 4, second)
        e.write(SUBWEAPON, AXE, "<i")
        reload_as(run, mb, ch)
        run.step(120)  # the module loads the weapons; they land

    def own_attack():
        """Richter's whip (his attack flag), or Maria's owl (an entity: her attack sets no flag)."""
        if ch == CHAR_RICHTER:
            return bool(e.read(ATTACK_NOW, "<H"))
        raw = e.read_bytes("g_Entities", 0xBC * 64)
        return any(struct.unpack_from("<H", raw, s * 0xBC + 0x54)[0] == 0x8011 for s in range(4, 64))  # ANIMSET_WPN_OWL

    def press(pad):
        """What the press did over the next 30 frames: (weapon ids seen, their own attack ran, hearts spent)."""
        e.write(HEARTS_NOW, 99, "<i")
        run.step(2, pad)
        ids, own = set(), False
        for _ in range(30):
            run.step(1)
            ids |= weapon_ids(e)
            own |= own_attack()
        spent = e.read(HEARTS_NOW, "<i") < 99
        for _ in range(120):  # until everything's over
            if not weapon_ids(e) and not own_attack():
                break
            run.step(1)
        run.step(60)  # the swing's recovery outlasts its sprites: a press then is lost, as Alucard's
        return ids, own, spent

    def sheet_is(hand):
        import struct
        y = 0x180 if ch != CHAR_RICHTER else 0x100
        rows = e.vram_rect(0x240, y, 0x40, 0x80)
        return b"".join(struct.pack("<64H", *r) for r in rows) == e.read_bytes(SHEET_COPIES + hand * 0x4000, 0x4000)

    holding(0, sword)
    ids, own, _ = press("square")
    run.expect(own and not ids, "nothing in the first hand: □ is their own attack", ids=sorted(ids), own=own)
    ids, own, _ = press("circle")
    run.expect(ids and min(ids) >= 0xF0, "a sword in the second: ○ swings it", ids=sorted(ids))

    holding(sword, 0)
    ids, own, _ = press("square")
    run.expect(ids and max(ids) < 0xF0 and not own, "a sword in the first hand: □ swings it, not their attack",
               ids=sorted(ids), own=own)
    ids, own, spent = press("up+square")
    run.expect(spent and not ids, "...and ↑+□ still throws the subweapon", ids=sorted(ids), spent=spent)
    ids, own, _ = press("circle")
    run.expect(not ids and not own, "...and ○, with nothing in the second hand, does nothing", ids=sorted(ids))

    holding(sword, club)
    ids, _, _ = press("square")
    first = sheet_is(0)
    ids2, _, _ = press("circle")
    second = sheet_is(1)
    ids3, _, _ = press("square")
    run.expect(ids and max(ids) < 0xF0 and ids2 and min(ids2) >= 0xF0 and ids3 and max(ids3) < 0xF0,
               "a weapon in each hand: □ and ○ each swing their own", square=sorted(ids), circle=sorted(ids2))
    run.expect(first and second and sheet_is(0), "each swing draws from its hand's sheet",
               first=first, second=second)

    holding(two_handed, two_handed)  # as the menu equips one
    ids, own, _ = press("square")
    ids2, own2, _ = press("circle")
    run.expect(ids and ids2 and not own and not own2, "a two-handed sword: both buttons swing it, no whip or owl",
               square=sorted(ids), circle=sorted(ids2))


FGAME_GFX_ADDR, FGAME_PAL_ADDR = 0x80580000, 0x806C2000  # module/coop_api.h: CoopBoot's F_GAME.BIN
PICS = (0x380, 0x181, 0x20, 0x7F)  # the familiar list's pictures: F_GAME.BIN's strip 0x1A


@per_character(only="richter")
def familiar_list_pictures(run, ch):
    """#298 (1.1.1 playtest): the familiar list showed no pictures for Richter and Maria. Their
    games load F_GAME2.BIN, which has none, and their own colours in the pictures' palettes. Here
    the pictures' corner is blanked (as their own load leaves it); with the menu open it holds
    Alucard's pictures and palettes, and when it closes their VRAM is as it was."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    x, y, w, h = PICS
    e.write_vram(x, y, [[0] * w for _ in range(h)])
    cluts = [e.read(SYMBOLS["g_ClutIds"] + (0x1D0 + k) * 2, "<H") for k in range(7)]
    pal = lambda: [e.vram_rect((c & 0x3F) << 4, c >> 6, 16, 1)[0] for c in cluts]
    before_pics, before_pal = e.vram_rect(x, y, w, h), pal()
    alu_pics = [struct.unpack_from(f"<{w}H", e.read_bytes(FGAME_GFX_ADDR + 0x1A * 0x2000 + r * w * 2, w * 2)) for r in range(h)]
    alu_pal = [struct.unpack_from("<16H", e.read_bytes(FGAME_PAL_ADDR + ((c >> 6) - 0xF0) * 0x200 + ((c & 0x3F) << 5), 32))
               for c in cluts]
    run.step(4, "start")
    run.step(90)
    run.expect(e.read("g_GameEngineStep") == 2, "the pause menu is open")
    run.expect([tuple(r) for r in e.vram_rect(x, y, w, h)] == [tuple(r) for r in alu_pics],
               "the familiars' pictures are Alucard's", blank_rows=sum(not any(r) for r in e.vram_rect(x, y, w, h)))
    run.expect([tuple(p) for p in pal()] == [tuple(p) for p in alu_pal], "...and their palettes")
    for _ in range(6):
        run.step(2, "triangle")
        run.step(30)
        if e.read("g_GameEngineStep") == 1:
            break
    run.step(10)
    run.expect(e.read("g_GameEngineStep") == 1, "the menu closed")
    run.expect(e.vram_rect(x, y, w, h) == before_pics and pal() == before_pal, "closed: their own VRAM is back")


ELEMENT_CURSE, CURSE_MARK, SFX_WRITE = 0x100, 0x80097BF8, 0x80139000  # D_80097BF8; g_sfxRingBufferWritePos


def _curse_hit(run, e, element=ELEMENT_CURSE):
    e.write(e.entity(0) + HIT_POINTS, 3, "<h")
    e.write(e.entity(0) + HIT_PARAMS, 2 | element, "<H")
    run.step(150)  # the hit reaction and invincibility


def _swing_sounds(run, e, presses=6):
    before = e.read(SFX_WRITE, "<h")
    for _ in range(presses):
        run.step(4, "square")
        run.step(30, "")
    return (e.read(SFX_WRITE, "<h") - before) & 0xFF


@per_character
def curse_stops_attacks(run, ch):
    """Issue 102: curse as Alucard has it. A curse hit keeps their attacks from coming out (□ swings
    nothing) for his time, and then they're back; immunity keeps it off."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    e.write(HP_NOW, 200, "<i")
    start = e.save_state()
    free = _swing_sounds(run, e)
    run.expect(free > 0, "uncursed, □ swings (with its sound)", sounds=free)
    e.load_state(start)
    _curse_hit(run, e)
    cursed = _swing_sounds(run, e)
    run.expect(cursed * 4 < free and e.read(CURSE_MARK, "<I") & 1, "cursed: □ swings nothing", sounds=cursed, free=free, mark=e.read(CURSE_MARK, "<I"))
    run.step(0x400)
    back = _swing_sounds(run, e)
    run.expect(back * 4 >= free * 3, "it wears off: □ swings again", sounds=back, free=free)
    e.load_state(start)
    e.write(ELEMENTS_IMMUNE, ELEMENT_CURSE, "<H")
    _curse_hit(run, e)
    run.expect(_swing_sounds(run, e) * 4 >= free * 3, "immune: no curse")


LEATHER_SHIELD = 5


def _guards(e):
    """Player-side entities (slots 16-63) that guard: hitbox state bit 4, as a held shield's."""
    raw = e.read_bytes(e.entity(0), 0xBC * 64)
    px = e.read(e.entity(0), "<h", 2)
    out = []
    for slot in range(16, 64):
        ent = raw[slot * 0xBC:(slot + 1) * 0xBC]
        if int.from_bytes(ent[0x26:0x28], "little") and int.from_bytes(ent[0x3C:0x3E], "little") & 4:  # hitboxState
            out.append((slot, int.from_bytes(ent[2:4], "little", signed=True) - px))
    return out


@per_character
def shield_guards(run, ch):
    """#214 (Tucker, 2026-11-19: Richter and Maria block with shields): a shield in the second hand,
    ○ held puts up its guard, as Alucard's does (its entity in front, guarding); let go, it's down,
    and they walk again."""
    e, mb = run.emu, mailbox(run)
    e.write(EQUIPMENT + 4, LEATHER_SHIELD)
    reload_as(run, mb, ch)
    run.step(120)
    run.expect(not _guards(e), "no guard to start")
    seen = []
    for _ in range(60):
        run.step(1, "circle")
        seen = seen or _guards(e)
    run.expect(seen, "○ held: the shield guards", guards=seen)
    from coop_env import TOOLS
    e.screenshot(str(TOOLS["out"] / f"shield_guard_{ch}.png"))
    run.step(30, "")
    run.expect(not _guards(e), "let go: no guard")
    x = e.snapshot()["x"]
    run.step(40, "right")
    run.expect(e.snapshot()["x"] != x, "and they walk again", x=x, now=e.snapshot()["x"])



@per_character
def damage_rate_first_hand(run, ch):
    """#310: a Short Sword in the first hand, swung with □: Richter and Maria within Alucard's rate
    (their swings ran their own time, and a press during one brought out the whip or owl too: 43
    damage a second for Richter, 36 for Maria, his 30)."""
    e, mb = run.emu, mailbox(run)
    rate, top = damage_a_second(run, e, mb, ch, hand=0)
    run.expect(ALUCARD_RATE * 0.7 < rate <= ALUCARD_RATE * 1.1,
               f"{rate:.0f} damage a second, {top} a hit: near Alucard's {ALUCARD_RATE}, not over")


ELEMENT_STONE = 0x200


@per_character
def stone_breaks_with_presses(run, ch):
    """Issue 102: stone as Alucard has it. A stone hit holds them still (walking does nothing),
    mashing buttons breaks it, and then they walk again; immunity keeps it off."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    e.write(HP_NOW, 200, "<i")
    run.step(60)
    start = e.save_state()
    e.write(e.entity(0) + HIT_POINTS, 3, "<h")
    e.write(e.entity(0) + HIT_PARAMS, 2 | ELEMENT_STONE, "<H")
    run.step(150)
    x = e.snapshot()["x"]
    run.step(40, "right")  # (holding it is one press)
    run.expect(e.snapshot()["x"] == x, "stoned: walking does nothing", x=x, now=e.snapshot()["x"])
    for _ in range(12):
        run.step(2, "cross")
        run.step(2, "")
    x = e.snapshot()["x"]
    run.step(40, "right")
    run.expect(e.snapshot()["x"] != x, "mashing breaks it: they walk again", x=x, now=e.snapshot()["x"])
    e.load_state(start)
    e.write(ELEMENTS_IMMUNE, ELEMENT_STONE, "<H")
    _curse_hit(run, e, ELEMENT_STONE)
    x = e.snapshot()["x"]
    run.step(40, "right")
    run.expect(e.snapshot()["x"] != x, "immune: no stone", x=x, now=e.snapshot()["x"])


@per_character
def movement_stuck_fall_rescued(run, ch):
    """#336: Richter ended up inside the floor at a room's bottom, falling without moving, for good.
    Pushed into the floor there with a fall's speed, they're back on the floor within 2 seconds. And
    standing still (Alucard first, then them) never counts as a stuck fall: no arrival."""
    e, mb = run.emu, mailbox(run)

    def stands(who):
        busy, vy = 0, set()
        for i in range(240):
            run.step(1)
            busy += bool(mb.self_presence().flags & BUSY)
            vy.add(e.read(e.entity(0) + 0x0C, "<i"))
        run.expect(not busy, f"{who} standing still: no rescue", busy_frames=busy, velocity_y=sorted(vy)[:4])
    run.step(60)
    stands("Alucard")
    reload_as(run, mb, ch)
    run.step(60)
    stands(NAMES[ch])
    p = mb.self_presence()
    ground = (p.ground_x, p.ground_y)
    pl = e.entity(0)
    ys = []
    sunk = e.read(pl + 0x06, "<h") + 24  # posY.i.hi: 24 px into the floor (the report's was)
    for i in range(300):
        if i < 100:  # held in the floor, falling (as the report's state was)
            e.write(pl + 0x06, sunk, "<h")
            e.write(pl + 0x0C, 7 << 16, "<i")  # velocityY: falling
        run.step(1)
        ys.append(mb.self_presence().y)
    p = mb.self_presence()
    run.expect(max(ys[:80]) >= ground[1] + 20, "he was in the floor", ys=ys[::15])
    run.expect(abs(p.y - ground[1]) <= 16 and abs(p.x - ground[0]) <= 32, "back on the floor where he stood",
               now=(p.x, p.y), ground=ground, ys=ys[::15])


RELICS_AT = 0x80097964  # g_Status.relics


def shown_message(e):
    """The module's last message (message.c), as text."""
    from module import symbols
    raw = e.read_bytes(symbols()["g_CoopMessageText"], 64)
    return "".join(chr(b + 0x20) for b in raw[:raw.index(0xFF)]) if 0xFF in raw else ""


@scenario(start="entrance", disc=COOP_DISC)
def relic_move_news_maria(run):
    """#372 (Tucker: "when Maria finds Soul of Wolf, is there a message that says blade dash
    unlocked?"): with relics unlocking her moves (the default), a relic that unlocks one names it
    as it's found, and nothing is said for what she already had."""
    from link.mailbox import CHAR_MARIA
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_MARIA)
    run.step(120)
    run.expect(shown_message(e) != "Blade dash unlocked", "nothing said before", shown=shown_message(e))
    e.write(RELICS_AT + SKILL_OF_WOLF, 1, "<B")  # found, as a relic orb or the partner's find does
    run.step(60)
    from coop_env import TOOLS
    e.screenshot(str(TOOLS["out"] / "relic_move_news_maria" / "blade-dash.png"))
    run.expect(shown_message(e) == "Blade dash unlocked", "Skill of Wolf: Blade dash unlocked", shown=shown_message(e))
