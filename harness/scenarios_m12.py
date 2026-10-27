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
GUARDIANS = {"owl": (0x240, 0x180), "cardinal": (0x260, 0x100), "dragon": (0x240, 0x100),
             "doll": (0x260, 0x180), "turtle": (0x2E0, 0x100), "cat": (0x2C0, 0x180)}


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


# --- M12b spike: off-hand weapons through the weapon's own overlay (D105) --------------------
from scenarios_m8 import HALL_ROOM, NO3, OFFHAND_ITEMS, enemies_hp, wait  # noqa: E402
from link.mailbox import BUSY, CHAR_RICHTER, CMD_ARRIVE, IN_PLAY  # noqa: E402

SPIKE_ITEMS = OFFHAND_ITEMS[:5] + ((97, "spear-like (estoc)"),)


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


def aim(e, i, reach=40, button="circle"):
    """Walk to the nearest enemy, face it, and swing (○) when it's in reach."""
    from session_m12 import enemies
    snap = e.snapshot()
    foes = enemies(e)
    if not foes:
        return "left" if (i // 120) % 2 else "right"
    x = snap["world_x"]
    ex = min((v[1] for v in foes.values()), key=lambda fx: abs(fx - x))
    way = "right" if ex > x else "left"
    if abs(ex - x) > reach:
        return way
    return way if i % 20 < 2 else (button if i % 20 == 4 else "")


def offhand_like_alucard(run, ch, button="circle"):
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    out = TOOLS["out"] / run.name
    out.mkdir(parents=True, exist_ok=True)
    start = e.save_state()
    results = {}
    for item, what in SPIKE_ITEMS:
        e.load_state(start)
        e.write(EQUIPMENT, item)
        reload_as(run, mb, ch)
        mb.command(CMD_ARRIVE, NO3, HALL_ROOM, 1300, 200)
        wait(run, lambda: (lambda p: p.room_id == HALL_ROOM and p.flags & IN_PLAY and not p.flags & BUSY)(
            mb.self_presence()), 900, "arrived in the hall")
        run.step(90)
        spawned = hit = shot = False
        lasted, ended = 0, None
        for i in range(1200):
            for slot, hp in enemies_hp(e).items():  # tough enemies: a hit shows, nobody dies
                if 0 < hp < 999:
                    e.write("g_Entities", 999, "<h", slot * 0xBC + 0x3E)
            before = enemies_hp(e)
            pad = aim(e, i, button=button)
            pin_target(e)
            run.step(1, pad)
            w = weapon_entities(e)
            if w:
                spawned = True
                lasted += 1
                if not shot and i % 40 == 8:
                    e.screenshot(out / f"{NAMES.get(ch, 'Alucard').lower()}-{what.split(' ')[0]}.png")
                    shot = True
            now = enemies_hp(e)
            if any(s in now and now[s] < hp == 999 for s, hp in before.items()):
                hit = True
            if spawned and hit and i % 40 == 39 and not w:
                ended = True
                break
        results[what] = dict(spawned=spawned, hit=hit, ended=bool(ended), frames=lasted)
    ok = sum(1 for r in results.values() if r["spawned"] and r["hit"] and r["ended"])
    run.expect(ok >= 5, "the weapon's own overlay: spawns, hits, ends (5 of 6 classes)", results=results)


@scenario(start="entrance", disc=COOP_DISC)
def m12b_offhand_like_alucard_richter(run):
    """D105 spike: Richter's off-hand runs the weapon's own overlay with Alucard's swing."""
    offhand_like_alucard(run, CHAR_RICHTER)


@scenario(start="entrance", disc=COOP_DISC)
def m12b_alucard_baseline(run):
    """The same weapons in Alucard's own hands (□): what the off-hand must match."""
    offhand_like_alucard(run, 0, "square")
