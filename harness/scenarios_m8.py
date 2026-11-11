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


@per_character
def level_up(run, ch):
    """M8b criterion 5: Richter and Maria level up from EXP like Alucard (HP grows too)."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    level, hp = e.read(LEVEL), e.read(HP_MAX)
    e.write(EXP, 5000)
    run.step(30)
    run.expect(e.read(LEVEL) > level and e.read(HP_MAX) > hp, f"{NAMES[ch]} levels up",
               level=(level, e.read(LEVEL)), hp_max=(hp, e.read(HP_MAX)))


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


@per_character
def mist_step(run, ch):
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
def spell_shortcuts(run):
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
NO3, HALL_ROOM = 0x41, 72  # the castle entrance's zombie hall (room 14,40)
OFFHAND_ITEMS = ((19, "short sword"), (86, "sword"), (27, "two-handed sword"), (128, "club"),
                 (85, "fist"), (133, "throwing weapon"))
LEATHER_SHIELD, POTION, APPLE = 5, 159, 30
ATTACK_NOW = 0x80072F66  # g_Player.unk46: an attack of the player's own is under way


def offhand_entity(e):
    """(slot, attack) of the off-hand swing: a weapon overlay's entity (0xE0-0xFF, D105), or None."""
    for slot in range(4, 0x40):
        a = e.entity(slot)
        if e.read(a, "<H", 0x26) >= 0xE0 and e.read(a, "<h", 0x40) > 0:
            return slot, e.read(a, "<h", 0x40)
    return None


def enemies_hp(e):
    raw = e.read_bytes("g_Entities", 0xBC * 256)
    return {s: struct.unpack_from("<h", raw, s * 0xBC + 0x3E)[0] for s in range(64, 256)
            if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0]}


@per_character
def offhand_weapons(run, ch):
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
            from scenarios_m12 import pin_target  # an enemy on the swing's hitbox (D105)
            pin_target(e)
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


@scenario(start="entrance", disc=COOP_DISC)
def offhand_crouching_swings_low_richter(run):
    """Issue 162: crouched, ○'s swing is Alucard's crouching one, lower than standing."""
    e, mb = run.emu, mailbox(run)
    e.write(EQUIPMENT, OFFHAND_ITEMS[0][0])
    reload_as(run, mb, CHAR_RICHTER)
    run.step(90)  # the module loads the weapon
    start = e.save_state()
    ys = {}
    for how, pad in (("standing", ""), ("crouching", "down")):
        e.load_state(start)
        run.step(20, pad)
        run.step(2, (pad + "+circle").strip("+"))
        y = None
        for _ in range(20):  # the hitbox's centre, once it has one
            run.step(1, pad)
            sw = offhand_entity(e)
            if sw and e.read(e.entity(sw[0]), "<B", 0x47):
                y = e.read(e.entity(sw[0]), "<h", 6) + e.read(e.entity(sw[0]), "<h", 0x12)
                break
        ys[how] = y
    run.expect(None not in ys.values(), "○ swings both ways", ys=ys)
    run.expect(None not in ys.values() and ys["crouching"] > ys["standing"], "crouched, the swing is lower", ys=ys)


@scenario(start="entrance", disc=COOP_DISC)
def offhand_one_attack_at_a_time_richter(run):
    """Issue 29: ○ waits for the whip to end, and the whip waits for ○'s swing: never both."""
    e, mb, ch = run.emu, mailbox(run), CHAR_RICHTER
    e.write(EQUIPMENT, OFFHAND_ITEMS[0][0])
    reload_as(run, mb, ch)
    run.step(90)  # the module loads the weapon
    run.step(2, "square")
    run.step(3)
    whipping = e.read(ATTACK_NOW, "<H")
    run.expect(whipping, "the whip is out", unk46=whipping)
    run.step(2, "circle")
    swung = False
    for _ in range(40):
        run.step(1)
        swung |= offhand_entity(e) is not None and e.read(ATTACK_NOW, "<H") != 0
    run.expect(not swung, "○ does nothing during the whip")
    for _ in range(120):
        if not e.read(ATTACK_NOW, "<H"):
            break
        run.step(1)
    run.step(30)
    run.step(1, "circle")
    run.step(3)
    run.expect(offhand_entity(e) is not None, "○ works once the whip is over")
    run.step(2, "square")
    both = False
    for _ in range(12):
        run.step(1)
        both |= bool(e.read(ATTACK_NOW, "<H")) and offhand_entity(e) is not None
    run.expect(not both, "the whip does nothing during the swing")


MENU_STR, ALUCARD_NAME = 0x800A8258, bytes.fromhex("212C3523213224FF")  # g_MenuStr; [0] is the status page's name
MENU_NAMES = {CHAR_RICHTER: b"\x32\x29\x23\x28\x34\x25\x32\xFF", CHAR_MARIA: b"\x2D\x21\x32\x29\x21\xFF"}


@per_character
def pause_menu_portrait(run, ch):
    """Issue 27: the status page shows the player's own name and cutscene portrait, and what the
    portrait overwrote in VRAM comes back when the menu closes."""
    from coop_env import TOOLS
    from link import portraits
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    data = portraits.read(COOP_DISC)
    run.expect(data and len(data) == 4 + 2 * (48 * 72 + 256), "they're read from the disc")
    e.write_bytes(portraits.PORTRAIT_ADDR, data)
    run.step(120)
    before = e.vram_rect(0x300, 0x180, 32, 96)
    run.step(4, "start")
    run.step(120)
    run.expect(e.read("g_GameEngineStep") == 2, "the menu is open")
    name = bytes(e.read_bytes(e.read(MENU_STR), len(MENU_NAMES[ch])))
    run.expect(name == MENU_NAMES[ch], f"it says {NAMES[ch]}", name=name.hex())
    run.expect(e.vram_rect(0x300, 0x180, 32, 96) != before, "the portrait is theirs")
    e.screenshot(TOOLS["out"] / run.name / "menu.png")
    for _ in range(6):
        run.step(2, "triangle")
        run.step(30)
        if e.read("g_GameEngineStep") == 1:
            break
    run.step(30)
    run.expect(e.read("g_GameEngineStep") == 1, "the menu closes")
    run.expect(e.vram_rect(0x300, 0x180, 32, 96) == before, "VRAM is as it was")
    run.expect(bytes(e.read_bytes(e.read(MENU_STR), 8)) == ALUCARD_NAME, "and so is the game's name")


WEAPON_SELF, WEAPON_CLUT_OFS = 0x80710000, 0x7020  # module/link.h: CoopWeapon
WEAPON_PRG, FRAMES_OFS, PAL_SIZE = 0x8017A000, 0x40, 0x20
OFFHAND_PALS, BANK_PAL_Y = 0x2D0, 0x1F0  # module/offhand.c


@scenario(start="entrance", disc=COOP_DISC)
def offhand_frame_palettes_richter(run):
    """Issue 65: each frame of an off-hand swing draws with the palette the weapon's frame asks
    for, as in Alucard's hands, not with Richter's own."""
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    bad, many = [], []
    for item, what in OFFHAND_ITEMS:
        e.load_state(start)
        e.write(EQUIPMENT, item)
        reload_as(run, mb, CHAR_RICHTER)
        run.step(90)  # the module loads the weapon
        seen = set()
        for i in range(120):
            run.step(1, "circle" if i % 40 == 0 else "")
            for slot in range(4, 0x40):
                ent = e.entity(slot)
                eid = e.read(ent, "<H", 0x26)
                if eid < 0xE0:
                    continue
                hand = int(eid >= 0xF0)
                prg, own = WEAPON_PRG + hand * 0x3000, WEAPON_SELF + hand * 0x8000
                pal, frame = e.read(ent, "<H", 0x16), e.read(ent, "<H", 0x56) & 0x7FFF
                if not OFFHAND_PALS <= pal < OFFHAND_PALS + 48 or not frame:
                    continue
                parts = e.read(prg + FRAMES_OFS + frame * 4)
                if not prg <= parts < prg + 0x3000:
                    continue
                clut = e.read(parts + 2 + 0xA, "<h")
                seen.add(clut)
                k = pal - OFFHAND_PALS + clut  # as RenderEntities adds them
                want = list(struct.unpack("<16H", e.read_bytes(own + WEAPON_CLUT_OFS + (k % 24) * PAL_SIZE, PAL_SIZE)))
                if list(e.vram_rect(k % 16 * 16, 512 + BANK_PAL_Y + k // 16, 16, 1)[0]) != want:
                    bad.append((what, i, frame, clut))
            if what == "sword" and i == 8:
                e.screenshot(TOOLS["out"] / run.name / "sword.png")
        many.append((what, sorted(seen)))
    run.expect(any(s for _, s in many), "swings were seen", many=many)
    run.expect(not bad, "every frame has its palette", bad=bad[:8], n=len(bad), many=many)
    run.expect(len(dict(many)["sword"]) > 1, "the sword really uses several", many=many)
    run.expect(e.read("g_ClutIds", "<H", 2 * OFFHAND_PALS) & 0x8000 == 0, "the table is the game's after drawing")


SERVANT_LOADED = 0x80073064  # g_ServantLoaded
HOLY_SYMBOL, BAT_CARD, GHOST_CARD = 14, 18, 19
FAERIE_CARD, DEMON_CARD, SWORD_CARD = 0x14, 0x15, 0x16
POISON_WATER = 0x8009744C  # g_unkGraphicsStruct.D_8009744C: the stage marks the player in poison water


@per_character
def familiar(run, ch):
    """M8b §3: the familiar cards work for Richter and Maria too. With a card on, the module loads
    the familiar after a load (their code runs from the expansion RAM, so it fits), it comes out,
    and they still play."""
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    for relic, fam in ((BAT_CARD, 1), (GHOST_CARD, 2), (FAERIE_CARD, 3), (DEMON_CARD, 4), (SWORD_CARD, 5)):
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


@per_character
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
    e.write(EQUIPMENT, LIBRARY_CARD)
    reload_as(run, mb, ch)
    run.step(60)
    run.step(1, "circle")
    for _ in range(1200):
        run.step(1)
        if e.read("g_StageId") == LIB and mb.self_presence().flags & IN_PLAY:
            break
    run.expect(e.read("g_StageId") == LIB, "they're in the Library", stage=e.read("g_StageId"))
    run.expect(e.read(EQUIPMENT) != LIBRARY_CARD, "the card is used up", hand=e.read(EQUIPMENT))


@per_character
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
PL_TIMERS = 0x80072F00                                 # g_Player.timers
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
    more = 10 if ch == CHAR_RICHTER else 5  # 10 on the guardian's own value, of which her attack is half
    run.expect(mail >= attack + more, f"Brilliant Mail: 10 more on the sub-weapon's attack (+{more} here)",
               attack=attack, mail=mail)
    off = with_gear([(ACC1, HEART_BROACH), (0x80097C0C, BRILLIANT_MAIL)], first, rules_off=RULE_NO_GEAR_EFFECTS)
    run.expect(off == (cost, attack), "gear effects off: neither", off=off, plain=(cost, attack))
    if ch == CHAR_RICHTER:
        holy = 3  # SUBWPN_HOLY_WATER (characters/richter-ps1/coop_ric.c)
        _, water = with_gear([], holy)
        _, stauro = with_gear([(ACC1, STAUROLITE)], holy)
        run.expect(water > 0 and stauro >= 2 * water - 2, "a Staurolite doubles holy water's attack", water=water, stauro=stauro)


@per_character
def poison_water(run, ch):
    """M8b §2: poison water hurts Richter and Maria without Holy Symbol, as it does Alucard, and
    not with it, nor with the castle's "Use Alucard's stats" off (their own games)."""
    from link.mailbox import OPT_NO_ALUCARD_STATS
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    start = e.save_state()
    for symbol in (False, True, "rule off"):
        e.load_state(start)
        mb.set_rules(off=OPT_NO_ALUCARD_STATS if symbol == "rule off" else 0)
        if symbol is True:
            e.write(STATUS, RELIC_ON, "<B", HOLY_SYMBOL)
        hp = e.read(HP_NOW, "<i")
        for _ in range(180):
            e.write(POISON_WATER, 8, "<i")
            run.step(1)
        lost = hp - e.read(HP_NOW, "<i")
        if symbol == "rule off":
            run.expect(lost == 0, "with Alucard's stats off, poison water doesn't hurt", lost=lost)
        elif symbol:
            run.expect(lost == 0, "with Holy Symbol, poison water doesn't hurt", lost=lost)
        else:
            run.expect(lost > 0, "without it, poison water hurts", lost=lost)


POISON_MARK = 0x80097BF8  # g_Status.D_80097BF8: bit 0, the game's own "poisoned"
ELEMENT_POISON, ELEMENTS_IMMUNE = 0x80, 0x80097C2C
DEFENSE = 0x80097C24  # g_Status.defenseEquip
HIT_POINTS, HIT_PARAMS, ENTITY_PALETTE = 0x3E, 0x44, 0x16
PAL_POISON = 0x8166  # PAL_FLAG(PAL_CC_DARK_EFFECT), as built


def _hit(run, e, damage, element=0):
    """The player takes a hit as the game's hit detection leaves it; returns the HP lost."""
    hp = e.read(HP_NOW, "<i")
    e.write(e.entity(0) + HIT_POINTS, damage, "<h")
    e.write(e.entity(0) + HIT_PARAMS, 2 | element, "<H")
    run.step(2)
    lost = hp - e.read(HP_NOW, "<i")
    run.step(150)  # his hit reaction and invincibility
    return lost


@per_character
def poison_hits(run, ch):
    """Issue 102: poison as Alucard has it. Immunity keeps it off; once poisoned, hits do double;
    the player pulses; it wears off."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, ch)
    e.write(HP_NOW, 200, "<i")
    start = e.save_state()
    e.write(ELEMENTS_IMMUNE, ELEMENT_POISON, "<H")
    _hit(run, e, 5, ELEMENT_POISON)
    run.expect(not e.read(POISON_MARK, "<I") & 1, "immune: not poisoned")
    e.load_state(start)
    first = _hit(run, e, 5, ELEMENT_POISON)
    run.expect(e.read(POISON_MARK, "<I") & 1, "a poison hit poisons")
    second = _hit(run, e, 5)
    d = e.read(DEFENSE, "<H")  # Alucard's stats rule: his defense comes off theirs too (#160)
    run.expect((first, second) == (max(1, 5 - d), max(1, 10 - d)), "hits do double while poisoned",
               first=first, second=second, defense=d)
    seen = False
    for _ in range(90):
        run.step(1)
        seen |= e.read(e.entity(0) + ENTITY_PALETTE, "<H") == PAL_POISON
    run.expect(seen, "the player pulses the poison palette")
    for _ in range(0x1000):
        run.step(1)
        if not e.read(POISON_MARK, "<I") & 1:
            break
    run.expect(not e.read(POISON_MARK, "<I") & 1, "it wears off")


@per_character
def alucard_health_bar(run, ch):
    """Issue 34: with the option on, Richter and Maria draw Alucard's bar, with his tiles."""
    from link.mailbox import OPT_ALUCARD_HUD
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    mb.set_options(OPT_ALUCARD_HUD)
    reload_as(run, mb, ch)
    run.step(120)
    out = TOOLS["out"] / run.name
    out.mkdir(parents=True, exist_ok=True)
    e.screenshot(out / "hud.png")
    bar = e.read(PRIM_BUF + e.read(PLAYER_HUD_PRIM, "<i") * PRIM_SIZE + PRIM_TPAGE, "<H")
    run.expect(bar == ALUCARD_HUD_TPAGE, "its first sprite is on Alucard's page", tpage=bar)


PLAYER_HUD_PRIM, PRIM_BUF, PRIM_SIZE, PRIM_TPAGE, ALUCARD_HUD_TPAGE = 0x80137970, 0x80086FEC, 0x34, 0x1A, 0x1F
SHORT_SWORD = 19
ALUCARD_RATE = 30  # damage_rate_alucard, measured


def damage_a_second(run, e, mb, ch, seconds=10):
    """Issue 114: mashing the plain attack at an enemy held on it, in the hall: swing rate,
    hitboxes and the target's invincibility, all counted the same way. Returns (damage a second,
    the most in one hit)."""
    from scenarios_m12 import pin_target
    e.write(EQUIPMENT, SHORT_SWORD)
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


@per_character
def damage_rate(run, ch):
    """Issue 114: what this character does a second."""
    e, mb = run.emu, mailbox(run)
    rate, top = damage_a_second(run, e, mb, ch)
    run.expect(ALUCARD_RATE * 0.7 < rate < ALUCARD_RATE * 1.3,
               f"{rate:.0f} damage a second, {top} a hit: near Alucard's {ALUCARD_RATE}")


@scenario(start="entrance", disc=COOP_DISC)
def damage_rate_alucard(run):
    """Issue 114: the yardstick: Alucard with a Short Sword, his weapon at Slogra and Gaibon."""
    e, mb = run.emu, mailbox(run)
    rate, top = damage_a_second(run, e, mb, 0)
    run.expect(abs(rate - ALUCARD_RATE) < 5, f"{rate:.0f} damage a second, {top} a hit", yardstick=ALUCARD_RATE)


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
def relic_gates_more(run, ch):
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


NO1, TELESCOPE_ROOM, TELESCOPE_X, TELESCOPE_Y = 0x01, 24, 339, 160  # the Outer Wall's foot (layout: E_ID_28)
E_TELESCOPE = 0x28
PLAYER_STATUS = 0x80072F2C - 0x80072BD0  # g_Player.status


@scenario(start="entrance", disc=COOP_DISC)
def telescope_alucard(run):
    """#173's control: Alucard still looks through the telescope (his compare is the game's own)."""
    telescope(run, CHAR_ALUCARD)


@per_character
def telescope(run, ch):
    """#173: Richter and Maria look through the telescope at the foot of the Outer Wall: standing
    at it and pressing Up starts it (its step goes past 1), as it does for Alucard."""
    e, mb = run.emu, mailbox(run)
    if ch != CHAR_ALUCARD:
        reload_as(run, mb, ch)
    mb.command(CMD_ARRIVE, NO1, TELESCOPE_ROOM, TELESCOPE_X + 48, TELESCOPE_Y - 40)
    wait(run, lambda: (lambda p: p.stage == NO1 and p.room_id == TELESCOPE_ROOM and p.flags & IN_PLAY and
                       not p.flags & BUSY)(mb.self_presence()), 900, "arrived by the telescope")
    run.step(90)
    scope = next((s for s in range(64, 256) if e.read(e.entity(s), "<H", 0x26) == E_TELESCOPE), None)
    run.expect(scope is not None, "the telescope is in the room")
    for _ in range(120):  # walk up to it (a wall stops Richter and Maria a few pixels sooner)
        if e.read(e.entity(0), "<h", 2) <= e.read(e.entity(scope), "<h", 2) + 2:
            break
        run.step(1, "left")
    run.step(20)
    standing = e.read("g_Player", "<I", PLAYER_STATUS)
    run.step(20, "up")
    step = e.read(e.entity(scope), "<H", 0x2C)
    run.expect(step >= 2, f"{NAMES.get(ch, 'Alucard')} looks through it", step=step, status=hex(standing),
               dx=e.read(e.entity(0), "<h", 2) - e.read(e.entity(scope), "<h", 2))


STR_TOTAL = 0x80097BD8  # g_Status.statsTotal[STAT_STR]


def richter_attacks(run, e, pad, frames=40):
    """The biggest attack value among his attack entities (slots 1-63) while doing this."""
    import struct
    best = 0
    run.step(2, pad)
    for _ in range(frames):
        run.step(1)
        raw = e.read_bytes("g_Entities", 0xBC * 64)
        for s in range(1, 64):
            if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0]:
                best = max(best, struct.unpack_from("<h", raw, s * 0xBC + 0x40)[0])
    return best


@scenario(start="entrance", disc=COOP_DISC)
def richter_blade_dash_damage(run):
    """Issue 190: under "Use Alucard's stats" his whip does Alucard's damage a second (D166), but
    Blade Dash kept its own attack and gained INT on top: 4 times the whip. Now his body's attacks
    keep his own game's ratio to the whip (Blade Dash 80 to 32), growing with STR as it does. With
    the rule off, both are his own game's."""
    from link.mailbox import OPT_NO_ALUCARD_STATS
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_RICHTER)
    mb.set_options(OPT_SHORTCUTS)
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    run.step(60)
    e.write(STATUS, RELIC_ON, "<B", SKILL_OF_WOLF)
    start = e.save_state()
    for off, what in ((0, "Alucard's stats"), (OPT_NO_ALUCARD_STATS, "his own game's")):
        e.load_state(start)
        mb.set_rules(off=off)
        run.step(2)
        strength = e.read(STR_TOTAL, "<i")
        whip = richter_attacks(run, e, "square")
        run.step(30)
        dash = richter_attacks(run, e, "r2")
        if off:
            run.expect((whip, dash) == (32, 80), f"{what}: the whip 32, Blade Dash 80", whip=whip, dash=dash)
        else:
            want = 32 * 20 // 100 + strength
            run.expect(whip == want, f"{what}: the whip is 20% of 32 plus STR", whip=whip, str=strength)
            run.expect(dash == want * 80 // 32, f"{what}: Blade Dash is 80/32 of that", dash=dash, want=want * 80 // 32)

