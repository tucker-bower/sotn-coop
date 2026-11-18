"""M5 acceptance tests: bosses together (design/M5-bosses-cutscenes.md).

The boss on the test route is the Doppleganger in the Outer Wall: its room (NO1 cells 57-58,
row 23) is a boss teleport, so walking into it from the room to its right (room 96) loads the
boss overlay."""

import struct

from session import session_scenario  # first: puts `link` on the path

from link.mailbox import BOSS, BUSY, CMD_ARRIVE, DEAD, IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST
from session_progress import arrive
from session_scenarios import heal

ENGINE_NORMAL, ENGINE_MENU = 1, 2
NO1 = 0x01
DEMO_TIMER = 0x32C  # g_Player.demo_timer
NEXT_TO_BOSS = (96, 40, 135)  # NO1 room 96 (59,23), near its left edge
DOPPLEGANGER10, DOPPLEGANGER10_HP = 253, 120  # enemy definition (assets/dra/us/enemydefs.yaml)


def bosses(g):
    """{slot: (enemyId, hp, step)} of living boss-type entities (only the Doppleganger here)."""
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    out = {}
    for slot in range(64, 256):
        e = raw[slot * 0xBC:(slot + 1) * 0xBC]
        eid, enemy, hp = struct.unpack_from("<H", e, 0x26)[0], struct.unpack_from("<H", e, 0x3A)[0], \
            struct.unpack_from("<h", e, 0x3E)[0]
        if eid and enemy == DOPPLEGANGER10:
            out[slot] = (enemy, hp, struct.unpack_from("<H", e, 0x2C)[0])
    return out


def toward(g, owner, slot, i):
    """A pad for g: walk at the boss (owner's world, slot) and attack when close."""
    raw = owner.read_bytes(owner.entity(slot), 0xBC)
    boss_x = struct.unpack_from("<h", raw, 2)[0] + owner.read("g_Tilemap", "<h", 0xA)
    me = g.snapshot()["world_x"]
    side = "right" if boss_x > me else "left"
    if abs(boss_x - me) > 28:  # close in first: Alucard stops walking to punch
        return side
    return side + "+square" if i % 12 < 2 else side


def into_boss_room(run, g, limit=1800):
    """g arrives next to the Doppleganger's room and walks in. Returns frames until its presence
    shows a boss fight, or None."""
    arrive(run, g, NO1, *NEXT_TO_BOSS)
    for i in range(limit):
        run.step(1, p1=("left", "") if g is run.s.a else ("", "left"))
        if i % 30 == 0:
            heal(g)
        if g.mailbox("self_presence").flags & BOSS:
            return i
    return None


def wait_pulled(run, g, other, limit=1200):
    """Steps until g is in other's room, in play. Returns frames, or None."""
    for i in range(limit):
        run.step(1)
        if i % 30 == 0:
            heal(run.s.a), heal(run.s.b)
        p, q = g.mailbox("self_presence"), other.mailbox("self_presence")
        if p.room == q.room and p.flags & IN_PLAY and not p.flags & BUSY:
            return i
    return None


NO0 = 0x00
LEFT_OF_MARIA = (80, 728, 135)  # NO0 room 80 (cells 29-31, row 26), near its right edge


# --- #188: a big hit in Richter's arena (BO6) left Richter and Maria in their hit pose for good -----
HIT_STEP = 10            # PL_S_HIT (src/ric/ric.h; Maria's and Alucard's Player_Hit are the same)
FLUNG = (2, 15)          # its step_s for a DAMAGEKIND_5 hit: flies until a wall (Alucard's is 15)
FLING_HIT = 5            # DAMAGEKIND_5: the possessed Richter's tackle and Blade Dash
BO6, BO6_ARRIVE = 0x18, (0, 128, 179)  # launcher/bossstarts.py: Richter's arena
PAUSE_ENEMIES = 0x80097400  # g_unkGraphicsStruct.pauseEnemies: his scenes hold him with it


def arena_fling(run, g, x, from_left, before=()):
    """g, at x in its arena, hit from that side, takes a hit like the possessed Richter's tackle
    (DAMAGEKIND_5: the fling), after playing the pads `before` (a jump: hit in the air). Returns
    (it was flung, frames until it was out of the hit, x then)."""
    def hold():  # in both games: the boss holds still, harmless, and nobody's HP runs out
        for h in (run.s.a, run.s.b):
            h.write(PAUSE_ENEMIES, 1)
            h.write("g_Status", h.read("g_Status", "<i", 0x240), "<i", 0x23C)
            raw = h.read_bytes("g_Entities", 0xBC * 256)
            for slot in range(64, 256):  # hitboxState: only the test's hit lands
                if raw[slot * 0xBC + 0x3C] or raw[slot * 0xBC + 0x3D]:
                    h.write(h.entity(slot), 0, "<H", 0x3C)
    hold()
    p0 = g.entity(0)
    hold()  # the boss holds still, and a hit of his already under way ends first:
    for _ in range(300):       # (issue 248: B was still in his tackle's hit, which isn't the fling)
        if g.read(p0, "<H", 0x2C) == 0:  # standing
            break
        run.step(1)
        hold()
    g.write(p0, x, "<h", 2)
    g.write("g_PlayerX", x + g.read("g_Tilemap", "<h", 0xA), "<i")
    g.write(p0, 1, "<H", 0x14)
    for pad in before:
        run.step(1, (pad, "") if g is run.s.a else ("", pad))
        hold()
    # the hit's direction comes from the last hitter (RicStepHit's func_80159C04: PLAYER.unkB8), his
    # Richter: he stands on the side it comes from, as for his tackle
    hitter = g.read(p0, "<I", 0xB8)
    if 0x80000000 <= hitter < 0x80200000:  # well clear of the player
        g.write(hitter, g.read(p0, "<h", 2) + (-100 if from_left else 100), "<h", 2)
    hold()                                    # the boss holds still: only this hit lands
    g.write_bytes("g_Player", bytes(32), 0x330)                  # g_Player.timers: no i-frames
    g.write(p0, 10, "<h", 0x3E)                                  # PLAYER.hitPoints
    g.write(p0, FLING_HIT, "<H", 0x44)                           # PLAYER.hitParams
    flung, seen = None, []
    for t in range(600):
        run.step(1)
        hold()
        step, step_s = g.read(p0, "<H", 0x2C), g.read(p0, "<H", 0x2E)
        if step == HIT_STEP:
            g.write(p0, 0, "<H", 0x44)  # taken: hit detection would clear it, but it's paused
        if not seen or seen[-1][1:3] != (step, step_s):
            seen = (seen + [(t, step, step_s, g.read(p0, "<h", 2), g.read("g_Status", "<i", 0x23C))])[:16]
        arena_fling.seen = seen
        if step == HIT_STEP and step_s in FLUNG:
            flung = t
        elif flung is not None and step != HIT_STEP:
            [h.write(PAUSE_ENEMIES, 0) for h in (run.s.a, run.s.b)]
            return True, t, g.read(p0, "<h", 2)
    [h.write(PAUSE_ENEMIES, 0) for h in (run.s.a, run.s.b)]
    return flung is not None, None, g.read(p0, "<h", 2)


def arena_edges(run):
    """Both players into Richter's arena (from the entrance's progress: no fight there, nothing else
    hits them), then each is flung into its right edge and must get up again (#188)."""
    from link.mailbox import CMD_ARRIVE
    from session_m15 import load_characters
    a, b = run.s.a, run.s.b
    load_characters(run)
    for g in (a, b):
        g.mailbox("command", CMD_ARRIVE, BO6, *BO6_ARRIVE)
    in_arena = lambda g: (lambda p: p.stage == BO6 and p.flags & IN_PLAY and not p.flags & BUSY)(
        g.mailbox("self_presence"))
    died = []
    for t in range(6000):  # his scene moves on while a direction is held
        if not died and a.read(a.entity(0), "<H", 0x2C) == 16:
            died.append((t, a.read("g_Status", "<i", 0x23C), a.read("g_CutsceneHasControl"), a.snapshot()))
        run.step(1, p1=("left", "left"))
        for g in (a, b):  # he fights as soon as it's over: they mustn't die waiting
            g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
        if all(in_arena(g) and not g.read("g_CutsceneHasControl") for g in (a, b)):
            break
    run.expect(all(in_arena(g) for g in (a, b)), "both are in Richter's arena, in play",
               a=a.snapshot(), b=b.snapshot())
    run.step(120)
    for g, who in ((a, "A"), (b, "B")):
        run.expect(g.read(g.entity(0), "<H", 0x2C) != 16, f"{who} is alive in the arena",
                   step=g.read(g.entity(0), "<H", 0x2C), hp=g.read("g_Status", "<i", 0x23C), at=g.snapshot(), died=died)
        for x, from_left in ((200, True),):  # the reports' edge; the left is the same code, mirrored
            flung, frames, x_after = arena_fling(run, g, x, from_left)
            run.expect(flung, f"{who} is flung by the hit (x {x})", x=x_after, seen=arena_fling.seen)
            run.expect(frames is not None, f"{who} gets up after hitting the arena's edge (x {x})",
                       x=x_after, step=g.read(g.entity(0), "<H", 0x2C), step_s=g.read(g.entity(0), "<H", 0x2E))
            run.expect(8 <= x_after <= 0xF8, f"{who} stays inside the arena's walls", x=x_after)
            run.step(120)


def _arena_test(name, characters, full):
    def test(run):
        arena_edges(run)
    test.__name__ = name
    test.__doc__ = ("Issue 188 (0.17.0): the possessed Richter's tackle or Blade Dash flung a player into his "
                    "arena's edge, which has no wall for Richter's or Maria's code, and they stayed in the hit "
                    "pose for good. Each player, flung into the edge, gets up.")
    session_scenario(starts=("entrance", "entrance"), characters=characters, full=full)(test)


_arena_test("boss_arena_edge_richter_and_maria", (1, 2), False)
_arena_test("boss_arena_edge_alucard_and_richter", (0, 1), True)


# --- #259: in the real fight, the possessed Richter's Blade Dash knocked a player back for good ----


# How a player is when his tackle lands: standing, crouched, at points of a jump, near either edge
FLING_POSES = {"standing": (), "crouched": ("down",) * 8, "jump rising": ("cross",) * 6,
               "jump top": ("cross",) * 16 + ("",) * 8, "jump falling": ("cross",) * 16 + ("",) * 22,
               "walking": ("right",) * 6, "attacking": ("square",) * 2 + ("",) * 4}


def arena_fling_poses(run):
    """#259: each player, in each pose, near each edge of Richter's arena and in its middle, flung
    toward and away from the edge: each gets up."""
    from link.mailbox import CMD_ARRIVE
    from session_m15 import load_characters
    a, b = run.s.a, run.s.b
    load_characters(run)
    for g in (a, b):
        g.mailbox("command", CMD_ARRIVE, BO6, *BO6_ARRIVE)
    in_arena = lambda g: (lambda p: p.stage == BO6 and p.flags & IN_PLAY and not p.flags & BUSY)(
        g.mailbox("self_presence"))
    for t in range(6000):
        run.step(1, p1=("left", "left"))
        for g in (a, b):
            g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
        if all(in_arena(g) and not g.read("g_CutsceneHasControl") for g in (a, b)):
            break
    run.expect(all(in_arena(g) for g in (a, b)), "both are in Richter's arena, in play")
    run.step(120)
    for h in (a, b):
        run.expect(h.read(h.entity(0), "<H", 0x2C) != 16, "alive in the arena", at=h.snapshot())
    bad, tried, flings = [], 0, 0
    for g, who in ((a, "A"), (b, "B")):
        for pose, before in FLING_POSES.items():
            for x in (12, 128, 244):
                for from_left in (True, False):
                    flung, frames, x_after = arena_fling(run, g, x, from_left, before)
                    tried, flings = tried + 1, flings + bool(flung)
                    # (a hit already under way, or a character whose code takes it as a plain
                    # knockback, isn't a fling: counted, not a failure)
                    if flung and (frames is None or not 8 <= x_after <= 0xF8):
                        bad.append((who, pose, x, "from left" if from_left else "from right", flung, frames,
                                    x_after, arena_fling.seen[-4:]))
                    for _ in range(30):  # settle, the boss still held and both kept alive
                        run.step(1)
                        for h in (a, b):
                            h.write(PAUSE_ENEMIES, 1)
                            h.write("g_Status", h.read("g_Status", "<i", 0x240), "<i", 0x23C)
    run.expect(flings >= tried * 3 // 4, "most of the hits fling", flings=flings, tried=tried)
    run.expect(not bad, "every fling ends with the player up, inside the arena", count=len(bad), bad=bad[:8])


def _poses_test(name, characters, full):
    def test(run):
        arena_fling_poses(run)
    test.__name__ = name
    test.__doc__ = ("Issue 259: the possessed Richter's tackle and Blade Dash fling a player until a wall. A "
                    "player hit in the air, crouched, walking or attacking, near either edge or in the middle, "
                    "flung either way, gets up inside the arena.")
    session_scenario(starts=("entrance", "entrance"), characters=characters, full=full)(test)


_poses_test("boss_arena_fling_poses_alucard_and_richter", (0, 1), True)
_poses_test("boss_arena_fling_poses_maria_and_alucard", (2, 0), True)
_poses_test("boss_arena_fling_poses_saturn_maria_and_saturn_richter", (4, 5), True)


# --- #283: Shaft's orb is seen and hit by each player's own Holy Glasses --------------------------
ORB_ID = 0x40  # BO6's Shaft orb (func_us_801C03E8)


def _orb(g):
    """(palette, hitboxState) of g's orb, or None while there's none. Told by its entity id: a guest's
    copy has no update of its own, and the authority's boss updates are wrapped (aggro)."""
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    for slot in range(64, 256):
        b = raw[slot * 0xBC:(slot + 1) * 0xBC]
        if int.from_bytes(b[0x26:0x28], "little") == ORB_ID and int.from_bytes(b[0x16:0x18], "little") in (0x810D, 0x8252):
            return int.from_bytes(b[0x16:0x18], "little"), int.from_bytes(b[0x3C:0x3E], "little")
    return None


def _ents(g):
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    return [(s, hex(int.from_bytes(raw[s * 0xBC + 0x26:s * 0xBC + 0x28], "little")),
             hex(int.from_bytes(raw[s * 0xBC + 0x28:s * 0xBC + 0x2C], "little")),
             hex(int.from_bytes(raw[s * 0xBC + 0x16:s * 0xBC + 0x18], "little")))
            for s in range(64, 256) if int.from_bytes(raw[s * 0xBC + 0x26:s * 0xBC + 0x28], "little")]


def orb_by_own_glasses(run):
    from link.mailbox import CMD_ARRIVE
    from module import symbols
    from scenarios_m12 import HEAD, HOLY_GLASSES, PAL_HIDDEN_FLAGGED, PAL_ORB_SEEN
    a, b = run.s.a, run.s.b
    full_hp = lambda: [g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C) for g in (a, b)]
    for g in (a, b):
        g.mailbox("command", CMD_ARRIVE, BO6, *BO6_ARRIVE)
    for _ in range(4200):  # the fight's opening, then the orb comes out (about 1800 frames)
        run.step(1)
        full_hp()
        if _orb(a) and _orb(b) and not any(g.read("g_CutsceneHasControl") for g in (a, b)):
            break
    run.expect(_orb(a) and _orb(b), "the orb is out in both games", a=a.snapshot(), b=b.snapshot(),
               ents_a=_ents(a)[:20], cs=[g.read("g_CutsceneHasControl") for g in (a, b)])
    owned = symbols()["g_CoopOrbsOwned"]
    roles = lambda: {g.mailbox("self_presence").role: g for g in (a, b)}
    AUTH, GUEST = ROLE_AUTHORITY, ROLE_GUEST
    for glasses_on in ("guest", "authority"):
        r = roles()
        run.expect(set(r) == {AUTH, GUEST}, "the room is shared: one authority, one guest", roles=sorted(r))
        auth, guest = r[AUTH], r[GUEST]
        wearer, other = (guest, auth) if glasses_on == "guest" else (auth, guest)
        wearer.write(HEAD, HOLY_GLASSES)
        other.write(HEAD, 0)
        before = guest.read(owned)
        seen = {}
        for _ in range(60):
            run.step(1)
            full_hp()
            seen = {"wearer": _orb(wearer), "other": _orb(other)}
        run.expect(seen["wearer"] and seen["wearer"][0] == PAL_ORB_SEEN and seen["wearer"][1],
                   f"Glasses on the {glasses_on}: it sees the orb, and can hit it", seen={k: v and tuple(map(hex, v)) for k, v in seen.items()})
        run.expect(seen["other"] and seen["other"][0] == PAL_HIDDEN_FLAGGED and not seen["other"][1],
                   "...and the player without them doesn't", seen={k: v and tuple(map(hex, v)) for k, v in seen.items()})
        run.expect(guest.read(owned) > before, "the guest's copy follows its own player", owned=guest.read(owned) - before)


@session_scenario(starts=("entrance", "entrance"))
def boss_richter_orb_by_own_glasses(run):
    """#283 (playtest 2026-11-14): in a shared room the guest copies the authority's orb, so it was
    seen and hit by the authority's player's Holy Glasses, never the guest's. With the Glasses on the
    guest only, then the authority only, the wearer sees the orb and can hit it, the other can't."""
    orb_by_own_glasses(run)


# --- #284: a player pausing mid-fight leaves one Richter on each screen ---------------------------
def _count(g, entity_id):
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    return sum(1 for s in range(64, 256) if int.from_bytes(raw[s * 0xBC + 0x26:s * 0xBC + 0x28], "little") == entity_id)


def pause_mid_fight(run):
    from link.mailbox import CMD_ARRIVE
    a, b = run.s.a, run.s.b
    full_hp = lambda: [g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C) for g in (a, b)]
    for g in (a, b):
        g.mailbox("command", CMD_ARRIVE, BO6, *BO6_ARRIVE)
    for _ in range(4200):
        run.step(1)
        full_hp()
        if _orb(a) and _orb(b) and not any(g.read("g_CutsceneHasControl") for g in (a, b)):
            break
    run.expect(_orb(a) and _orb(b), "the fight is on in both games, the orb out", a=a.snapshot(), b=b.snapshot())
    richter = a.read(a.entity(64), "<H", 0x26)  # BO6's RIC (g_Entities[STAGE_ENTITY_START]): his entity id
    roles = {g.mailbox("self_presence").role: g for g in (a, b)}
    run.expect(set(roles) == {ROLE_AUTHORITY, ROLE_GUEST}, "the room is shared", roles=sorted(roles))
    for who in (ROLE_AUTHORITY, ROLE_GUEST):
        g = roles[who]
        pad = lambda p: (p, "") if g is a else ("", p)
        name = "the authority" if who == ROLE_AUTHORITY else "the guest"
        run.step(2, p1=pad("start"))
        counts = []
        for t in range(600):
            run.step(1)
            full_hp()
            if t % 20 == 0:
                counts.append((_count(a, richter), _count(b, richter), bool(_orb(a)), bool(_orb(b))))
        # The report's moment: its afterimage (BO6's slots 65-67, no entity id) drawn when it paused
        for slot, frame in ((66, 126), (67, 126)):
            g.write(g.entity(slot), 32, "<h", 2)
            g.write(g.entity(slot), 126, "<h", 6)
            g.write(g.entity(slot), frame, "<h", 0x56)
            g.write(g.entity(slot), 0x8001, "<H", 0x14)
        run.step(2, p1=pad("start"))
        for t in range(600):
            run.step(1)
            full_hp()
            if t % 20 == 0:
                counts.append((_count(a, richter), _count(b, richter), bool(_orb(a)), bool(_orb(b))))
        run.capture()
        if g.mailbox("self_presence").role == ROLE_GUEST:  # back as the room's guest: nothing of its own drawn
            stale = [s for s in (65, 66, 67) if g.read(g.entity(s), "<h", 0x56) and not g.read(g.entity(s), "<H", 0x26)]
            run.expect(not stale, f"{name}, back as the guest, has no frozen Richter left (#284)", stale=stale)
        run.expect(all(ra == 1 and rb == 1 for ra, rb, _, _ in counts), f"{name} paused, then went on: one Richter in each game",
                   counts=sorted(set(counts)))
        run.expect(counts[-1][2] and counts[-1][3], f"...and the orb is out in both after", counts=counts[-5:])


@session_scenario(starts=("entrance", "entrance"))
def boss_richter_pause_keeps_one_richter(run):
    """#284 (playtest 2026-11-14): a player pausing mid-fight left a frozen Richter on its own screen,
    beside the moving one: his afterimages (BO6's slots 65-67, entities with no id) aren't in a
    snapshot, and a game back as the guest kept the ones it drew when it paused. The authority, then
    the guest, pauses for 10 seconds (an afterimage drawn) and goes on: one Richter in each game, the
    orb still out, and no afterimage left frozen in the guest."""
    pause_mid_fight(run)


LIFE_UP_SPAWN = 0x1D  # BO4's EntityLifeUpSpawn: the reward's light, 385 primitives in one chain
LIFE_UP_PRIMS = 385


def _chain(g, slot):
    """The length of the primitive chain of g's entity in slot, or 0."""
    e = g.read_bytes(g.entity(slot), 0xBC)
    if not struct.unpack_from("<I", e, 0x34)[0] & 0x800000:  # FLAG_HAS_PRIMS
        return 0
    base = g.addr("g_PrimBuf")
    at, n = base + struct.unpack_from("<h", e, 0x64)[0] * 0x34, 0
    while at and n < 0x500:
        n += 1
        at = g.read(at, "<I") & 0xFFFFFFFF
    return n


@session_scenario(starts=("no1", "entrance"))
def boss_reward_survives_hand_over(run):
    """The authority beats the Doppleganger; while the reward's light plays (385 primitives in one
    chain), it leaves the room and the other game takes the room over. The chain it takes over is
    whole, and the game doesn't crash (#288: a snapshot could say 319 at most, and both games of
    the 1.1.1 playtest wrote through a null pointer into low memory)."""
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    run.expect(wait_pulled(run, b, a, 600) is not None, "B is pulled into the boss room")
    run.step(30)
    roles = {g: g.mailbox("self_presence").role for g in (a, b)}
    auth = next((g for g in (a, b) if roles[g] == ROLE_AUTHORITY), None)
    run.expect(auth is not None, "one game holds the room", roles={g.name: r for g, r in roles.items()})
    guest = b if auth is a else a
    for slot in bosses(auth):  # harness shortcut: one hit left
        auth.write(auth.entity(slot), 1, "<h", 0x3E)
    pad = lambda inp: (inp, "") if auth is a else ("", inp)
    living = lambda: [s for s, (_, hp, _) in bosses(auth).items() if hp > 0]
    for i in range(1800):
        if not living():
            break
        run.step(1, p1=pad(toward(auth, auth, living()[0], i)))
        if i % 20 == 0:
            heal(a), heal(b)
    run.expect(not living(), "the boss is beaten", frames=i)
    slot = None
    for i in range(600):
        run.step(1)
        slot = next((s for s in range(64, 256) if guest.read(guest.entity(s), "<H", 0x26) == LIFE_UP_SPAWN), None)
        if slot is not None and _chain(auth, slot) >= LIFE_UP_PRIMS:
            break
    run.expect(slot is not None, "the guest shows the reward's light", frames=i)
    run.expect(_chain(auth, slot) >= LIFE_UP_PRIMS, "the authority's chain is whole", n=_chain(auth, slot))
    auth.mailbox("command", CMD_ARRIVE, NO1, *NEXT_TO_BOSS)  # leaves the room at once
    took = None
    for i in range(600):
        run.step(1)
        if guest.mailbox("self_presence").role != ROLE_GUEST:
            took = i
            break
    run.expect(took is not None, "the other game takes the room over", frames=i)
    alive = guest.read(guest.entity(slot), "<H", 0x26) == LIFE_UP_SPAWN
    run.expect(alive, "the reward's light is still playing at the hand-over")
    run.expect(_chain(guest, slot) >= LIFE_UP_PRIMS, "the chain it takes over is whole",
               n=_chain(guest, slot))
    run.step(600)  # the light runs to its end in this game (a crash fails the test by itself)
    p = guest.mailbox("self_presence")
    run.expect(p.flags & IN_PLAY and not p.flags & DEAD, "that game plays on", flags=p.flags)
