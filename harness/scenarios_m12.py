"""M12 single-game tests (design/M12-coverage.md): playtest 2026-10-25 note 4, Maria's guardians."""

from link.mailbox import CHAR_ALUCARD, CHAR_MARIA
from module import COOP_DISC
from scenario import scenario
from scenarios_m8 import EQUIPMENT, LEATHER_SHIELD, NAMES, mailbox, reload_as
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


@scenario(start="entrance", disc=COOP_DISC)
def maria_guardians_keep_their_graphics(run):
    """Playtest 2026-10-25 note 4: Maria's birds turned into a skull and a shield. A weapon or shield
    in her other hand must not overwrite her guardians' graphics."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_MARIA)
    run.step(60)
    before = vram(e)
    for item, what in ((SHORT_SWORD, "a short sword"), (LEATHER_SHIELD, "a shield")):
        e.write(EQUIPMENT, item)
        e.write(EQUIPMENT + 4, item)  # both hands: both weapon slots load
        reload_as(run, mb, CHAR_MARIA)
        run.step(120)
        after = vram(e)
        changed = [n for n, (x, y) in GUARDIANS.items() if block(before, x, y) != block(after, x, y)]
        run.expect(not changed, f"{what} in her hands: her guardians' graphics are intact", changed=changed)


AXE = 2  # Richter's subweapon ids; Maria's code turns the axe into her cardinal
ANIMSET_WPN_CARDINAL = 0x8014  # ANIMSET_OVL(20), src/maria/maria.h
SUBWEAPON, HEARTS = 0x80097BFC, 0x80097BA8  # g_Status.subWeapon, .hearts


def cardinals(e):
    import struct
    raw = e.read_bytes("g_Entities", 0xBC * 256)
    return sum(1 for s in range(256) if struct.unpack_from("<H", raw, s * 0xBC + 0x54)[0] == ANIMSET_WPN_CARDINAL)


@scenario(start="entrance", disc=COOP_DISC)
def maria_keeps_throwing(run):
    """Playtest 2026-10-25 note 4: after a while, Maria stopped throwing anything. Her cardinal,
    thrown again and again (hearts kept up), with weapons in and out of her other hand between
    rounds: every throw makes a bird. (Her cardinal, alone of her guardians, can't be thrown while
    she moves or is in the air: src/maria/pl_setstep.c MarDoSubweapon. Each throw here is made
    standing.)"""
    e, mb = run.emu, mailbox(run)
    rounds = []
    for r, item in enumerate((0, SHORT_SWORD, 0, LEATHER_SHIELD, SHORT_SWORD, 0, 0, 0)):
        e.write(EQUIPMENT, item)
        e.write(SUBWEAPON, AXE, "<i")
        reload_as(run, mb, CHAR_MARIA)
        run.step(120)  # she lands (a weapon's load pauses the game a moment)
        birds = 0
        for k in range(8):  # walk a little, stop, throw
            run.step(20, "left" if k % 2 else "right")
            run.step(20)
            e.write(HEARTS, 99, "<i")
            run.step(2, "up+square")
            for _ in range(30):
                run.step(1)
                if cardinals(e):
                    birds += 1
                    break
        rounds.append(birds)
    run.expect(all(n == 8 for n in rounds), "every standing throw makes a bird, weapon in hand or not", rounds=rounds)


# --- off-hand weapons through the weapon's own overlay (D105): helpers ------------------------
# (The M12b spike's 6-weapon tests are gone: the hand-item tests below cover all 72, item by item.)
from scenarios_m8 import HALL_ROOM, NO3, enemies_hp, wait  # noqa: E402
from link.mailbox import BUSY, CHAR_RICHTER, CMD_ARRIVE, IN_PLAY  # noqa: E402


def weapon_entities(e):
    """Slots 4-63 holding a weapon overlay's entity (ids 0xE0-0xFF): {slot: animSet}."""
    import struct
    raw = e.read_bytes("g_Entities", 0xBC * 64)
    return {s: struct.unpack_from("<H", raw, s * 0xBC + 0x54)[0] for s in range(4, 64)
            if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0] >= 0xE0}


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
IVE_BEEN_ROBBED = 53
WEAPON_CATEGORIES = (0, 1, 2, 3, 4, 5)  # short sword, sword, thrown, fist, club, two-handed


def hand_weapons(e):
    raw = e.read_bytes(EQUIP_DEFS, EQUIP_SIZE * N_HAND_ITEMS)
    return [i for i in range(1, N_HAND_ITEMS) if raw[i * EQUIP_SIZE + CATEGORY_OFS] in WEAPON_CATEGORIES]


def try_weapon(run, mb, ch, item, button, frames=400):
    """Equip, go to the hall, swing at an enemy kept on the live hitbox: (spawned, hit, ended)."""
    e = run.emu
    e.write(EQUIPMENT, item)
    e.write("g_CastleFlags", 0, "<B", IVE_BEEN_ROBBED)  # the Alucard Sword: else a load takes it, as Death did
    reload_as(run, mb, ch)
    mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)
    wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
        mb.self_presence()), 900, "arrived in the hall")
    run.step(90)
    spawned = hit = ended = False
    for i in range(frames):
        for slot, hp in enemies_hp(e).items():
            if 0 < hp < 999:
                e.write("g_Entities", 999, "<h", slot * 0xBC + 0x3E)
        before = enemies_hp(e)
        pin_target(e)
        run.step(1, button if i % 60 == 0 else "")
        w = weapon_entities(e)
        spawned |= bool(w)
        now = enemies_hp(e)
        hit |= any(s in now and now[s] < hp == 999 for s, hp in before.items())
        if spawned and not w and i % 60 > 40:
            ended = True
            if hit:
                break
    return spawned, hit, ended


def hand_items(run, ch, button, part):
    """Half the hand weapons (part 0 or 1: every other one), so the halves run side by side."""
    e, mb = run.emu, mailbox(run)
    start = e.save_state()
    items = hand_weapons(e)[part::2]
    results = {}
    for item in items:
        e.load_state(start)
        results[item] = try_weapon(run, mb, ch, item, button)
    import json
    from coop_env import TOOLS
    (TOOLS["out"] / run.name).mkdir(parents=True, exist_ok=True)
    (TOOLS["out"] / run.name / "items.json").write_text(json.dumps(results))
    bad = {i: r for i, r in results.items() if not (r[0] and r[2])}
    run.expect(not bad, f"every hand weapon ({len(items)}) spawns and ends", bad=bad)
    return results


def _hand_items_test(ch, name, button, part):
    def test(run):
        _against_alucard(run, hand_items(run, ch, button, part))
    test.__name__ = f"hand_items_{name}_{part + 1}"
    test.__doc__ = (f"Every other hand weapon (half {part + 1}) in {name.capitalize()}'s hands, against "
                    "Alucard's results (D105; Alucard's: harness/data/hand_items_alucard.json).")
    scenario(start="entrance", disc=COOP_DISC, full=name != "alucard")(test)  # Richter's, Maria's: --full


for _part in (0, 1):
    _hand_items_test(0, "alucard", "square", _part)
    _hand_items_test(CHAR_RICHTER, "richter", "circle", _part)
    _hand_items_test(2, "maria", "circle", _part)  # CHAR_MARIA


def _against_alucard(run, results):
    """Alucard's own results are the reference (his weapons are the game's own code): kept in
    harness/data/, so the characters' halves needn't wait for his run. If his change, that file
    is updated on purpose, after a look at why."""
    import json
    from pathlib import Path
    ref = json.loads((Path(__file__).parent / "data/hand_items_alucard.json").read_text())
    alu = {int(k): v for k, v in ref.items()}
    differ = {i: (alu.get(i), list(r)) for i, r in results.items() if list(r) != alu.get(i)}
    run.expect(not differ, "the same as Alucard's reference, item by item", differ=differ)


# --- the test castles the app ships (D136) ---------------------------------------------------
from pathlib import Path  # noqa: E402
MOD = Path(__file__).resolve().parent.parent  # this repo (coop_env's REPO is the decomp's)
from link.mailbox import CMD_LOAD_SAVE  # noqa: E402
import savestates as route  # noqa: E402

@scenario(start="entrance", disc=COOP_DISC)
def test_castles_bundled(run):
    """Every test castle in launcher/assets/test-castles, as a playtester gets it (its memory card
    header blanked: scripts/export_test_castles.py): its save loads, the player arrives at its
    start, and a bot walking on meets its boss, or its scene starts. (The Lesser Demon's start
    needs mist through bars: the bot starts past them, as the debug start's own check does.)"""
    import json
    import sys
    from link.mailbox import BOSS, CUTSCENE, IN_PLAY
    sys.path.insert(0, str(MOD / "launcher"))
    import bossstarts
    from bots import walker
    e, mb = run.emu, mailbox(run)
    bundle = MOD / "launcher" / "assets" / "test-castles"
    index = json.loads((bundle / "index.json").read_text())["castles"]
    rows = {f"Boss: {b['name']}": b for b in bossstarts.B} | {f"Scene: {b['name']}": b for b in bossstarts.S}
    base = e.save_state()
    bad = []
    playing = lambda: (lambda q: q.flags & IN_PLAY and not q.flags & BUSY)(mb.self_presence())
    for name, v in sorted(index.items(), key=lambda kv: kv[1]["order"]):
        b = rows[name]
        e.load_state(base)
        mb.put_save((bundle / v["save"]).read_bytes())
        mb.command(CMD_LOAD_SAVE)
        if not (wait_for(run, lambda: e.read("g_GameState") == route.GAME_NOW_LOADING, 600) and
                wait_for(run, lambda: e.read("g_GameState") == route.GAME_PLAY and  # (the Nightmare and
                         (playing() or mb.self_presence().flags & CUTSCENE), 3000)):  # Dracula's open with a scene)
            bad.append((name, "the save didn't load"))
            continue
        stage, room, x, y = v["start"]
        if b.get("check"):
            room, x, y = b["check"]
        mb.command(CMD_ARRIVE, stage, room, x, y)
        if not wait_for(run, lambda: mb.self_presence().stage == stage and mb.self_presence().room_id == room, 1200):
            bad.append((name, "never arrived", e.snapshot()))
            continue
        run.step(60)
        bot = walker(b["walk"], attack_every=0)
        reached = ((lambda: e.read("g_CutsceneHasControl")) if b.get("scene")  # (the Librarian's isn't shared)
                   else (lambda: mb.self_presence().flags & BOSS))
        if not wait_for(run, reached, 7200, bot):
            bad.append((name, "no boss or scene", e.snapshot()))
    run.expect(not bad, f"all {len(index)} test castles load and reach their boss or scene", bad=bad)


def wait_for(run, cond, frames, bot=None):
    for i in range(frames):
        if cond():
            return True
        run.step(1, bot(run.emu.snapshot(), i) if bot else "")
    return False


GAME_PROLOGUE_END = 7  # g_GameState: the prologue's text crawl (src/dra/game_handlers.c)
CRAWL_STEP, CRAWL_SKIP_STEP = 6, 16  # PrologueScroll's steps: the crawl, its fade-out


@scenario(start="st0_end", disc=COOP_DISC)
def prologue_crawl_skips_on_start(run):
    """#159: after Dracula falls, Start skips the prologue's text crawl, even on a castle that has
    never seen it (the game itself skips only once it has: 110 s every new castle)."""
    e = run.emu
    for i in range(6000):
        if e.read("g_GameState") == GAME_PROLOGUE_END and e.read("g_GameStep") == CRAWL_STEP:
            break
        run.step(1)
    run.expect(e.read("g_GameStep") == CRAWL_STEP, "the text crawl started", frames=i, state=e.read("g_GameState"))
    seen, cleared = e.read("g_Settings", "<i", 0x10C) & 2, e.read("g_GameClearFlag", "<i")
    run.expect(not seen and not cleared, "the game itself wouldn't let it be skipped", seen=seen, cleared=cleared)
    run.step(120)
    run.expect(e.read("g_GameStep") == CRAWL_STEP, "it runs on by itself (not yet skipped)")
    run.step(2, "start")
    run.step(4)
    run.expect(e.read("g_GameStep") >= CRAWL_SKIP_STEP or e.read("g_GameState") != GAME_PROLOGUE_END,
               "Start skipped it", step=e.read("g_GameStep"), state=e.read("g_GameState"))
    for i in range(3000):
        if e.read("g_StageId") == 0x41 and e.read("g_GameState") == 2:
            break
        run.step(1)
    run.expect(e.read("g_StageId") == 0x41, "and the castle's entrance comes next", frames=i)



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
        e.write(EQUIPMENT, item)
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
