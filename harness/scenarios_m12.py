"""M12 single-game tests (design/M12-coverage.md): playtest 2026-10-25 note 4, Maria's guardians."""

from link.mailbox import CHAR_ALUCARD, CHAR_MARIA
from module import COOP_DISC
from scenario import scenario
from scenarios_m8 import EQUIPMENT, LEATHER_SHIELD, mailbox, reload_as
from vram_survey import VRAM_W, vram

SHORT_SWORD = 19
# Maria's guardians in VRAM (src/maria/ovl_load.c, the PS1 layout): x, y in 16-bit words, 32x128
# each. A hand weapon's graphics load at x 0x240-0x27F, y 0x100-0x17F (right hand) and 0x180-0x1FF
# (left hand: src/dra/cd.c), over four of them.
# The doll (0x260, 0x180) can't be selected in our port, and with the owl's spot it holds her
# off-hand weapon's sheet (D106); the owl, her attack, moves out of its way (maria_owl_*).
GUARDIANS = {"cardinal": (0x260, 0x100), "dragon": (0x240, 0x100), "turtle": (0x2E0, 0x100),
             "cat": (0x2C0, 0x180)}


def block(v, x, y, w=0x20, h=0x80):
    return b"".join(v[2 * (row * VRAM_W + x):2 * (row * VRAM_W + x + w)] for row in range(y, y + h))


AXE = 2  # Richter's subweapon ids; Maria's code turns the axe into her cardinal
SUBWEAPON, HEARTS = 0x80097BFC, 0x80097BA8  # g_Status.subWeapon, .hearts


# --- off-hand weapons through the weapon's own overlay (D105): helpers ------------------------
# (The M12b spike's 6-weapon tests are gone: the hand-item tests below cover all 72, item by item.)
from scenarios_m8 import HALL_ROOM, NO3, enemies_hp, wait  # noqa: E402
from link.mailbox import BUSY, CHAR_RICHTER, CMD_ARRIVE, IN_PLAY  # noqa: E402


def pin_target(e):
    """While a weapon entity's hitbox is live, put an enemy (the toughest) right on it: tests that
    the weapon deals its damage, whatever the room's enemies are like (the castle entrance's are too
    low for a sword's stab). Returns the target's slot, or None."""
    import struct
    raw = e.read_bytes("g_Entities", 0xBC * 256)
    weapon = None
    for s in range(4, 64):
        o = s * 0xBC
        if struct.unpack_from("<H", raw, o + 0x26)[0] >= 0xE0 and raw[o + 0x46] and raw[o + 0x47]:
            weapon = o
            break
    if weapon is None:
        return None
    foes = [(struct.unpack_from("<h", raw, t * 0xBC + 0x3E)[0], t) for t in range(64, 256)
            if struct.unpack_from("<H", raw, t * 0xBC + 0x26)[0] and 0 < struct.unpack_from("<h", raw, t * 0xBC + 0x3E)[0] < 32767]
    if not foes:
        return None
    t = max(foes)[1] * 0xBC
    offx, offy = struct.unpack_from("<hh", raw, weapon + 0x10)
    facing = raw[weapon + 0x14]
    wx, wy = struct.unpack_from("<h", raw, weapon + 2)[0], struct.unpack_from("<h", raw, weapon + 6)[0]
    tox, toy = struct.unpack_from("<hh", raw, t + 0x10)
    e.write("g_Entities", wx + (-offx if facing else offx) - tox, "<h", t + 2)
    e.write("g_Entities", wy + offy - toy, "<h", t + 6)
    return t // 0xBC


# --- M12 part 3: every hand weapon in every character's hands --------------------------------
EQUIP_DEFS, EQUIP_SIZE, CATEGORY_OFS, N_HAND_ITEMS = 0x800A4B04, 0x34, 0x0E, 0xA9
WEAPON_CATEGORIES = (0, 1, 2, 3, 4, 5)  # short sword, sword, thrown, fist, club, two-handed


# --- the test castles the app ships (D136) ---------------------------------------------------
from pathlib import Path  # noqa: E402
MOD = Path(__file__).resolve().parent.parent  # this repo (coop_env's REPO is the decomp's)
from link.mailbox import CMD_LOAD_SAVE  # noqa: E402
import savestates as route  # noqa: E402


def wait_for(run, cond, frames, bot=None):
    for i in range(frames):
        if cond():
            return True
        run.step(1, bot(run.emu.snapshot(), i) if bot else "")
    return False


GAME_PROLOGUE_END = 7  # g_GameState: the prologue's text crawl (src/dra/game_handlers.c)
CRAWL_STEP, CRAWL_SKIP_STEP = 6, 16  # PrologueScroll's steps: the crawl, its fade-out


JEWEL_KNUCKLES = 97
ANIMSET_WPN_OWL = 0x8011  # ANIMSET_OVL(17): the owl her attack throws (src/maria/maria.h)
OWL_HOME, OWL_COPY = (0x240, 0x180), (0x1C0, 0x180)  # module/offhand.c


def owl_shot(run, e):
    """Attacks (□) and returns her owl a few frames into its flight, alone (the pixels it draws,
    against the same frame without it), 48 px around it; or None."""
    import struct
    from PIL import Image, ImageChops
    run.step(2, "square")
    for f in range(30):
        run.step(1)
        raw = e.read_bytes("g_Entities", 0xBC * 64)
        for s in range(1, 64):
            o = s * 0xBC
            if f < 6 or not struct.unpack_from("<H", raw, o + 0x26)[0] or \
                    struct.unpack_from("<H", raw, o + 0x54)[0] != ANIMSET_WPN_OWL:
                continue
            x, y = struct.unpack_from("<h", raw, o + 2)[0], struct.unpack_from("<h", raw, o + 6)[0]
            box = (x - 24, y - 24, x + 24, y + 24)
            s0 = e.save_state()
            run.step(1)
            with_owl = e.screenshot().convert("RGB").crop(box)
            e.load_state(s0)
            e.write("g_Entities", 0, "<H", o + 0x54)
            run.step(1)
            without = e.screenshot().convert("RGB").crop(box)
            mask = ImageChops.difference(with_owl, without).convert("L").point(lambda v: 255 if v else 0)
            return Image.composite(with_owl, Image.new("RGB", with_owl.size), mask)
    return None


@scenario(start="entrance", disc=COOP_DISC)
def maria_owl_with_a_weapon_in_hand(run):
    """Issue 203: with a weapon in a hand, Maria's attack (her owl) was garbage: the weapon's sheet
    goes over the owl's graphics (D106). The owl moves to a free spot and is drawn from there: it
    looks the same with Jewel Knuckles (the report's) or a sword in hand as with none."""
    from PIL import ImageChops
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    shots = {}
    for item, what in ((0, "empty hands"), (JEWEL_KNUCKLES, "Jewel Knuckles"), (SHORT_SWORD, "a short sword")):
        e.load_state(start)
        e.write(EQUIPMENT + 4, item)  # the second hand: □ is her owl (D209)
        reload_as(run, mb, CHAR_MARIA)
        run.step(60)
        if not item:
            owl = block(vram(e), *OWL_HOME)
        else:
            run.expect(block(vram(e), *OWL_COPY) == owl, f"{what}: her owl's graphics are at their copy")
        shots[item] = owl_shot(run, e)
        run.expect(shots[item] is not None, f"{what}: her attack throws an owl")
    for item, what in ((JEWEL_KNUCKLES, "Jewel Knuckles"), (SHORT_SWORD, "a short sword")):
        diff = ImageChops.difference(shots[0], shots[item]).getbbox()
        run.expect(diff is None, f"{what} in hand: her owl looks as it does empty-handed", diff=diff)


MAR_FRAMES = 124  # module/character.h
BO2, ARENA = 0x1C, 0  # the Colosseum's arena (Minotaur and Werewolf), Richter on its throne


def throne_scene(run, e, mb, character):
    """Sends the player into the Colosseum's arena and walks in until Richter's scene ends. Returns
    (frames of the scene, frames she had a pose she lacks, VRAM blocks written during the scene)."""
    from vram_survey import used_blocks
    from coop_env import TOOLS
    e.load_state_file(TOOLS["out"].parent / "fixtures" / "debug-starts" / "Boss - Minotaur and Werewolf.state")
    reload_as(run, mb, character)
    mb.command(CMD_ARRIVE, BO2, ARENA, 24, 160)
    arrived = lambda: ((mb.self_presence().room_left, mb.self_presence().room_top) == (19, 22)
                       and mb.self_presence().flags & IN_PLAY)
    wait(run, arrived, 900, "she arrives in the arena")
    scene = alien = 0
    first = None
    for _ in range(3000):  # she walks in; the scene takes her from there
        cut = e.read("g_CutsceneHasControl")
        if scene and not cut:
            break
        scene += bool(cut)
        if e.read("g_Entities", "<H", 0x56) & 0x7FFF >= MAR_FRAMES:
            alien += 1
            if first is None:
                first = vram(e)
        run.step(1, "right")
    last = vram(e)
    changed = set()
    if first is not None:
        changed = used_blocks(bytes(a ^ b for a, b in zip(first, last)))
    return scene, alien, changed


@scenario(start="entrance", disc=COOP_DISC)
def maria_scene_richter_on_the_throne(run):
    """Issue 209: in the Colosseum, the scene with Richter on the throne gives the player one of
    Alucard's poses (frame 0xBF). Maria has 123 frames: hers read past her table's end, she wasn't
    drawn, and the arena's floor and windows turned to garbage. Now she's drawn standing, and her
    game writes no VRAM in the scene that Alucard's doesn't."""
    e = run.emu
    mb = mailbox(run)
    _, _, alucard = throne_scene(run, e, mb, CHAR_ALUCARD)
    scene, alien, maria = throne_scene(run, e, mb, CHAR_MARIA)
    run.expect(scene, "Richter's scene plays", frames=scene)
    run.expect(alien, "the scene gives her a pose she doesn't have", frames=alien)
    extra = sorted(maria - alucard)
    run.expect(not extra, "her game writes no VRAM Alucard's doesn't in the scene",
               extra=[(hex(x * 64), hex(y * 32)) for x, y in extra])


BAT_CARD, FAERIE_CARD, SWORD_CARD = 18, 0x14, 0x16
FAM_HOME, FAM_BANK_COPY = (0x2C0, 0x100), (0x100, 0x100 + 512)  # module/familiar.c: page 0x100,0x100 of the second bank
MAR_HUD = (0x2C0, 0x100)  # her HUD set (src/maria/ovl_load.c), in the familiar's page with the turtle and cat
NO0, LEFT_OF_MARIA = 0x00, (80, 728, 135)  # session_m5: the Marble Gallery, another stage


def familiar_sheet(e, x, y):
    """A familiar's graphics, as src/dra/cd.c loads them: 0x40 x 0x80 words, then 0x20 x 0x80 below."""
    return e.vram_rect(x, y, 0x40, 0x80) + e.vram_rect(x, y + 0x80, 0x20, 0x80)


@scenario(start="entrance", disc=COOP_DISC)
def familiar_graphics_maria(run):
    """Issue 208: Maria's Bat came out garbled after changing areas: a familiar's graphics share a
    texture page with her HUD set, turtle and cat, and her init puts the HUD set back at each stage.
    Hers stay hers, the familiar's are in VRAM's second bank (as Alucard's game loads them), and
    both stay so across a stage change. The Bat (the report's), the Faerie (which fills the page) and
    the Sword (drawn with primitives)."""
    from scenarios_m8 import STATUS, RELIC_ON
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    reload_as(run, mb, CHAR_MARIA)
    run.step(120)
    mine = {n: e.vram_rect(x, y, 0x20, 0x80) for n, (x, y) in
            {"HUD set": MAR_HUD, "turtle": GUARDIANS["turtle"], "cat": GUARDIANS["cat"]}.items()}
    for card, name in ((BAT_CARD, "Bat"), (FAERIE_CARD, "Faerie"), (SWORD_CARD, "Sword")):
        e.load_state(start)
        e.write(STATUS, RELIC_ON, "<B", card)
        reload_as(run, mb, CHAR_ALUCARD)
        run.step(300)
        theirs = familiar_sheet(e, *FAM_HOME)  # as Alucard's game has it
        e.load_state(start)
        e.write(STATUS, RELIC_ON, "<B", card)
        reload_as(run, mb, CHAR_MARIA)
        for where in ("after a load", "after changing areas"):
            if where != "after a load":
                mb.command(CMD_ARRIVE, NO0, *LEFT_OF_MARIA)
                wait(run, lambda: mb.self_presence().stage == NO0 and mb.self_presence().flags & IN_PLAY
                     and not mb.self_presence().flags & BUSY, 1200, "she arrives in the Marble Gallery")
            run.step(300)
            changed = [n for n, (x, y) in {"HUD set": MAR_HUD, "turtle": GUARDIANS["turtle"],
                                            "cat": GUARDIANS["cat"]}.items() if e.vram_rect(x, y, 0x20, 0x80) != mine[n]]
            run.expect(not changed, f"{name}, {where}: her HUD set, turtle and cat are hers", changed=changed)
            run.expect(familiar_sheet(e, *FAM_BANK_COPY) == theirs,
                       f"{name}, {where}: its graphics are in the second bank, as Alucard's game has them")
            fam = [s for s in range(4, 64) if 0xD0 <= e.read(e.entity(s), "<H", 0x26) < 0xE0]
            run.expect(fam, f"{name}, {where}: it's out")
            if fam:  # evidence: the familiar on screen, 4x
                x, y = e.read(e.entity(fam[0]), "<h", 2), e.read(e.entity(fam[0]), "<h", 6)
                out = TOOLS["out"] / run.name
                e.screenshot().crop((x - 32, y - 32, x + 32, y + 32)).resize((256, 256)).save(
                    out / f"{name}_{where.split()[-1]}.png")


BO6_STAGE = 0x18  # include/game.h STAGE_BO6: the Castle Keep's Richter fight
HEAD, HOLY_GLASSES = 0x80097C08, 0x22  # g_Status.equipment[2]; the Holy Glasses (us_3E79C.c's check)
PAL_HIDDEN_FLAGGED, PAL_ORB_SEEN = 0x810D, 0x8252


@scenario(start="entrance", disc=COOP_DISC)
def shaft_orb_unseen_richter(run):
    """Issue 189: without the Holy Glasses, Shaft's orb can't be hit (the bad ending's way), and the
    game draws it with a palette that's blank for Alucard: Richter saw it. Now it isn't drawn for
    him; with the glasses on it's drawn, and can be hit, as for Alucard."""
    import struct
    from module import symbols
    from scenarios_m8 import HP_NOW
    e, mb = run.emu, mailbox(run)
    hidden = symbols()["g_CoopOrbsHidden"]
    start = e.save_state()
    for glasses in (0, HOLY_GLASSES):
        e.load_state(start)
        e.write(HEAD, glasses)
        reload_as(run, mb, CHAR_RICHTER)
        mb.command(CMD_ARRIVE, BO6_STAGE, 0, 128, 179)
        wait(run, lambda: mb.self_presence().stage == BO6_STAGE and mb.self_presence().flags & IN_PLAY,
             1500, "he arrives in Richter's arena")
        before = e.read(hidden)
        orbs = set()
        for _ in range(3000):  # the orb comes out after the fight's opening (about 1800 frames)
            run.step(1)
            raw = e.read_bytes("g_Entities", 0xBC * 256)
            orbs |= {struct.unpack_from("<H", raw, s * 0xBC + 0x16)[0] for s in range(64, 256)
                     if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0]} & {PAL_HIDDEN_FLAGGED, PAL_ORB_SEEN}
            e.write(HP_NOW, 80, "<i")
        kept_out = e.read(hidden) - before
        if glasses:
            run.expect(PAL_ORB_SEEN in orbs and not kept_out, "with the glasses: the orb is out, and drawn",
                       palettes=sorted(map(hex, orbs)), hidden=kept_out)
        else:
            run.expect(PAL_HIDDEN_FLAGGED in orbs, "without them: the orb is out, unseeable", palettes=sorted(map(hex, orbs)))
            run.expect(kept_out > 900, "...and it isn't drawn for Richter", hidden=kept_out)


POT_ROAST = 0x43
LEFT_SHEET_COPY = 0x80704000  # module/offhand.c SHEET(1): the left hand's sheet, kept in the 8MB


@scenario(start="entrance", disc=COOP_DISC)
def richter_left_hand_keeps_his_graphics(run):
    """Issue 195 (and 161): any item in Richter's left hand garbled his whip: DRA loads the left
    hand's graphics at 0x240,0x180, where his whip's links and effects are. His stay his with food,
    a shield or a sword there; with the sword, ○ swings it from its own sheet, now in the right hand's
    area (which he doesn't use)."""
    import struct
    from link.mailbox import CHAR_RICHTER
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    reload_as(run, mb, CHAR_RICHTER)
    run.step(120)
    his = block(vram(e), 0x240, 0x180, 0x40, 0x80)
    rich = e.save_state()
    for item, what in ((POT_ROAST, "a Pot Roast"), (LEATHER_SHIELD, "a shield")):  # as the menu equips them
        e.load_state(rich)
        e.write(EQUIPMENT + 4, item)
        run.step(2, "start")
        run.step(60)
        run.step(2, "start")
        run.step(120)
        run.expect(block(vram(e), 0x240, 0x180, 0x40, 0x80) == his, f"{what} in his left hand: his graphics are his")
    for hand, name in ((4, "left"), (0, "right")):  # #161: a weapon equipped, then taken off again
        e.load_state(rich)
        for item in (SHORT_SWORD, 0):
            e.write(EQUIPMENT + hand, item)
            run.step(2, "start")
            run.step(60)
            run.step(2, "start")
            run.step(120)
        run.expect(block(vram(e), 0x240, 0x180, 0x40, 0x80) == his,
                   f"a sword on and off his {name} hand: his graphics are his")
    for item, what in ((SHORT_SWORD, "a short sword"),):  # as a load equips it
        e.load_state(start)
        e.write(EQUIPMENT + 4, item)
        reload_as(run, mb, CHAR_RICHTER)
        run.step(120)
        run.expect(block(vram(e), 0x240, 0x180, 0x40, 0x80) == his, f"{what} in his left hand: his graphics are his")
    sheet = e.read_bytes(LEFT_SHEET_COPY, 0x40 * 0x80 * 2)
    run.expect(block(vram(e), 0x240, 0x100, 0x40, 0x80) == sheet, "the sword's sheet is in the right hand's area")
    drawn = set()
    run.step(1, "circle")
    for _ in range(40):
        run.step(1)
        raw = e.read_bytes("g_Entities", 0xBC * 64)
        drawn |= {struct.unpack_from("<H", raw, s * 0xBC + 0x5A)[0] for s in range(4, 64)
                  if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0] >= 0xF0}
    run.expect(drawn == {0x64}, "○ swings it, drawn from there (tpage 0x64)", unk5a=sorted(map(hex, drawn)))


NP3, NP3_ROOM = 0x07, 120  # the castle entrance, second visit: Bloody Zombies (report 20261107-222730)


@scenario(start="entrance", disc=COOP_DISC)
def stage_palettes_maria(run):
    """Issues 206, 164: with Richter or Maria playing, enemies drawn with palettes 0x2D0-0x2FF (the
    Bloody Zombie: 0x2D6) were invisible or in a weapon's colours: the off-hand weapons borrowed
    those entries for the whole drawing pass. Now only for the weapons' own: the zombie draws, in
    the stage's colours for it."""
    import struct
    from scenarios_m8 import HP_NOW
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_MARIA)
    mb.command(CMD_ARRIVE, NP3, NP3_ROOM, 142, 136)
    wait(run, lambda: mb.self_presence().stage == NP3 and mb.self_presence().flags & IN_PLAY
         and not mb.self_presence().flags & BUSY, 1200, "she arrives where the zombies are")
    run.step(90)  # the room fades in
    found = []
    for k in range(1200):
        run.step(1)
        e.write(HP_NOW, 80, "<i")
        raw = e.read_bytes("g_Entities", 0xBC * 256)
        for s in range(64, 256):
            o = s * 0xBC
            pal = struct.unpack_from("<H", raw, o + 0x16)[0]
            x, y = struct.unpack_from("<h", raw, o + 2)[0], struct.unpack_from("<h", raw, o + 6)[0]
            if (struct.unpack_from("<H", raw, o + 0x26)[0] and struct.unpack_from("<H", raw, o + 0x56)[0] and
                    0x2D0 <= (pal & 0x3FF) < 0x300 and 24 < x < 232 and 24 < y < 216):
                found.append((s, x, y, pal))
        if found:
            break
    run.expect(found, "an enemy with a palette in 0x2D0-0x2FF comes on screen", seen=found[:1])
    if not found:
        return
    s, x, y, pal = found[0]
    box = (x - 32, y - 48, x + 32, y + 32)
    # its palettes' colours (5 bits a channel), as the stage loaded them: its own and the next few,
    # which its sprite's parts add (the zombie's body is 0x2D8)
    v = vram(e)
    colors = set()
    for q in range(pal & 0x3FF, (pal & 0x3FF) + 8):
        clut = e.read("g_ClutIds", "<H", 2 * q)
        o = 2 * (((clut >> 6) & 0x1FF) * VRAM_W + (clut & 0x3F) * 16)
        colors |= {(c & 31, (c >> 5) & 31, (c >> 10) & 31) for c in struct.unpack_from("<16H", v, o)[1:] if c & 0x7FFF}
    run.step(1)
    shot = e.screenshot().convert("RGB").crop(box)
    drawn = sum(1 for r, g, b in shot.getdata() if (r >> 3, g >> 3, b >> 3) in colors)
    run.expect(drawn > 50, f"it's drawn (palette {pal:#x})", pixels=drawn, colors=len(colors))


# --- F9 reports: the game's own hitbox viewer, and what last hurt the player ------------------
@scenario(start="entrance", disc=COOP_DISC)
def report_f9_hitboxes_and_last_hit(run):
    """F9 adds each screen with DRA's hitbox viewer on (report.hitboxes) and what last hurt each
    player (report.last_hit). The picture differs from the same frames without it, the viewer is
    off again after, and an enemy put on the player is the one named."""
    import struct
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
    import report
    e = run.emu
    run.step(120)
    start = e.save_state()
    run.step(report.HITBOX_FRAMES)
    plain = e.screenshot().convert("RGB")
    e.load_state(start)
    boxes = report.hitboxes([e], lambda: run.step(1))[0].convert("RGB")
    changed = sum(1 for a, b in zip(plain.getdata(), boxes.getdata()) if a != b)
    from coop_env import TOOLS
    (TOOLS["out"] / run.name).mkdir(parents=True, exist_ok=True)
    boxes.save(TOOLS["out"] / run.name / "hitboxes.png")
    run.expect(changed > 100, "the hitboxes are drawn over the game", pixels=changed)
    run.expect((e.read(report.DEBUG_ENABLED), e.read(report.HITBOX_MODE)) == (0, 0), "and the viewer is off again")
    # In the hall (its zombies), an enemy with an attack, put on the player until it touches him
    mb = mailbox(run)
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    hurt = None
    for _ in range(600):
        raw = e.read_bytes("g_Entities", 0xBC * 256)
        foes = [s for s in range(64, 256) if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0]
                and struct.unpack_from("<h", raw, s * 0xBC + 0x40)[0] > 0 and raw[s * 0xBC + 0x3C]]
        if foes:
            px, py = struct.unpack_from("<h", raw, 2)[0], struct.unpack_from("<h", raw, 6)[0]
            e.write("g_Entities", px, "<h", foes[0] * 0xBC + 2)
            e.write("g_Entities", py, "<h", foes[0] * 0xBC + 6)
        run.step(1)
        hit = report.last_hit(e)
        if hit and foes and hit["slot"] == foes[0]:
            hurt = hit
            break
    run.expect(hurt is not None, "the enemy put on the player is the last thing that hurt him", hit=hurt)
