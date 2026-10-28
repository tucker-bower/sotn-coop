"""M12 single-game tests (design/M12-coverage.md): playtest 2026-10-25 note 4, Maria's guardians."""

from link.mailbox import CHAR_MARIA
from module import COOP_DISC
from scenario import scenario
from scenarios_m8 import EQUIPMENT, LEATHER_SHIELD, NAMES, mailbox, reload_as
from vram_survey import VRAM_W, vram

SHORT_SWORD = 19
# Maria's guardians in VRAM (src/maria/ovl_load.c, the PS1 layout): x, y in 16-bit words, 32x128
# each. A hand weapon's graphics load at x 0x240-0x27F, y 0x100-0x17F (right hand) and 0x180-0x1FF
# (left hand: src/dra/cd.c), over four of them.
# The owl and doll (0x240/0x260, 0x180) can't be selected in our port (no subweapon maps to them),
# and their area holds her off-hand weapon's sheet (D106): the four she uses are checked.
GUARDIANS = {"cardinal": (0x260, 0x100), "dragon": (0x240, 0x100), "turtle": (0x2E0, 0x100),
             "cat": (0x2C0, 0x180)}


def block(v, x, y, w=0x20, h=0x80):
    return b"".join(v[2 * (row * VRAM_W + x):2 * (row * VRAM_W + x + w)] for row in range(y, y + h))


@scenario(start="entrance", disc=COOP_DISC)
def m12_maria_guardians_keep_their_graphics(run):
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
def m12_maria_keeps_throwing(run):
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
WEAPON_CATEGORIES = (0, 1, 2, 3, 4, 5)  # short sword, sword, thrown, fist, club, two-handed


def hand_weapons(e):
    raw = e.read_bytes(EQUIP_DEFS, EQUIP_SIZE * N_HAND_ITEMS)
    return [i for i in range(1, N_HAND_ITEMS) if raw[i * EQUIP_SIZE + CATEGORY_OFS] in WEAPON_CATEGORIES]


def try_weapon(run, mb, ch, item, button, frames=400):
    """Equip, go to the hall, swing at an enemy kept on the live hitbox: (spawned, hit, ended)."""
    e = run.emu
    e.write(EQUIPMENT, item)
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
    test.__name__ = f"m12_hand_items_{name}_{part + 1}"
    test.__doc__ = (f"Every other hand weapon (half {part + 1}) in {name.capitalize()}'s hands, against "
                    "Alucard's results (D105; Alucard's: harness/data/hand_items_alucard.json).")
    scenario(start="entrance", disc=COOP_DISC)(test)


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
