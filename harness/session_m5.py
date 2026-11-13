"""M5 acceptance tests: bosses together (design/M5-bosses-cutscenes.md).

The boss on the test route is the Doppleganger in the Outer Wall: its room (NO1 cells 57-58,
row 23) is a boss teleport, so walking into it from the room to its right (room 96) loads the
boss overlay."""

import struct

from session import session_scenario  # first: puts `link` on the path

from link.mailbox import BOSS, BUSY, DEAD, IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST
from session_progress import arrive, status
from session_scenarios import heal

ENGINE_NORMAL, ENGINE_MENU = 1, 2
NO1 = 0x01
DEMO_TIMER = 0x32C  # g_Player.demo_timer
NEXT_TO_BOSS = (96, 40, 135)  # NO1 room 96 (59,23), near its left edge
DOPPLEGANGER10, DOPPLEGANGER10_HP = 253, 120  # enemy definition (assets/dra/us/enemydefs.yaml)
BOSS_STAGES = set(range(0x16, 0x1F)) | set(range(0x36, 0x3F))


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


@session_scenario(starts=("no1", "entrance"))
def boss_pulls_partner_in(run):
    """M5 criteria 1-2: A walks into the Doppleganger's room; B (at the castle entrance) is
    pulled in within 5 s. The boss has twice its HP, in both worlds."""
    a, b = run.s.a, run.s.b
    t = into_boss_room(run, a)
    run.expect(t is not None, "A is in a boss fight", frames=t, stage=hex(a.snapshot()["stage"]))
    run.expect(a.snapshot()["stage"] in BOSS_STAGES, "in the boss overlay", stage=hex(a.snapshot()["stage"]))
    hp = [e[1] for e in bosses(a).values()]
    run.expect(hp and max(hp) == 2 * DOPPLEGANGER10_HP, "the Doppleganger has twice its HP", hp=hp)
    t = wait_pulled(run, b, a, 300)
    run.expect(t is not None, "B was pulled in within 5 s", frames=t, b=str(b.mailbox("self_presence").room))
    run.step(30)
    roles = (a.mailbox("self_presence").role, b.mailbox("self_presence").role)
    run.expect(roles == (ROLE_AUTHORITY, ROLE_GUEST), "A runs the fight, B is its guest", roles=roles)
    run.expect(b.read("g_Player", "<i", DEMO_TIMER) == 0, "the boss's door doesn't hold the guest (#129)",
               hold=b.read("g_Player", "<i", DEMO_TIMER))
    run.expect([e[1] for e in bosses(b).values()] == [e[1] for e in bosses(a).values()],
               "B sees the same boss, with the same HP", a=bosses(a), b=bosses(b))


@session_scenario(starts=("no1", "entrance"))
def boss_no_escape_by_map(run):
    """M5 part 1: in a boss fight, ✕ on the map doesn't teleport away."""
    from session_travel import map_teleport
    a, b = run.s.a, run.s.b
    t = into_boss_room(run, a)
    run.expect(t is not None, "A is in a boss fight", frames=t)
    room = a.mailbox("self_presence").room
    map_teleport(run, a)
    run.step(240)
    run.expect(a.mailbox("self_presence").room == room, "A is still in the boss room", room=str(room))


@session_scenario(starts=("no1", "entrance"))
def boss_both_hit_one_death(run):
    """M5 criterion 3: both players damage the boss; it dies once; the kill is recorded in both
    worlds (the boss room's teleport checks that record)."""
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    run.step(30)
    slot, (_, hp0, _) = next(iter(bosses(a).items()))
    hit_by = set()
    for i in range(3600):
        before = bosses(a).get(slot, (0, 0, 0))[1]
        who = (i // 300) % 2  # take turns: A for 5 s, then B
        g = a if who == 0 else b
        pad = toward(g, a, slot, i)
        run.step(1, p1=(pad, "") if who == 0 else ("", pad))
        if i % 20 == 0:
            heal(a), heal(b)
        after = bosses(a).get(slot, (0, 0, 0))[1]
        if after < before:
            hit_by.add("AB"[who])
        if slot not in bosses(a) or after <= 0:
            break
        if len(hit_by) == 2:
            a.write(a.entity(slot), 1, "<h", 0x3E)  # both have hit it: finish it (harness shortcut)
    run.expect(hit_by == {"A", "B"}, "both players hurt the boss", hit_by=sorted(hit_by))
    for i in range(1800):  # its death sequence
        run.step(1)
        if not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & BOSS:
            break
    run.expect(not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & BOSS,
               "the fight is over in both worlds", frames=i, a=bosses(a), b=bosses(b))
    run.step(120)
    rec = lambda g: [g.read("g_Settings", "<i", 0x30 + 4 * k) for k in range(32)]
    ra, rb = rec(a), rec(b)
    run.expect(any(ra) and ra == rb, "the kill is recorded in both worlds",
               a=[i for i, v in enumerate(ra) if v], b=[i for i, v in enumerate(rb) if v])


def close_menu(run, g):
    pad = (lambda p: (p, "")) if g is run.s.a else (lambda p: ("", p))
    for p in ("triangle", "start", "triangle"):
        if g.read("g_GameEngineStep") == ENGINE_NORMAL:
            break
        run.step(2, **{"p1": pad(p)})
        run.step(60)
    run.expect(g.read("g_GameEngineStep") == ENGINE_NORMAL, "the menu closed", engine=g.read("g_GameEngineStep"))


@session_scenario(starts=("no1", "entrance"))
def boss_pause_keeps_the_partner_fighting(run):
    """Issue 108, D158: a pause works the same in a boss fight. Either player can open their menu;
    their game is frozen, so nothing hurts them, the other fights on, and the paused player comes
    back to the fight as it now is, whichever game was running it."""
    a, b = run.s.a, run.s.b
    run.expect(into_boss_room(run, a) is not None, "A is in a boss fight")
    run.expect(wait_pulled(run, b, a, 300) is not None, "B was pulled in")
    run.step(30)
    for paused, plays, who in ((b, a, "guest"), (a, b, "authority")):
        run.step(1, **{"p1": ("", "start") if paused is b else ("start", "")})
        run.step(60)
        run.expect(paused.read("g_GameEngineStep") == ENGINE_MENU, f"the {who} is in its menu")
        hp = status(paused)["hp"]
        heal(plays)
        x0, boss0 = plays.snapshot()["world_x"], bosses(plays)
        run.expect(len(boss0) == 1, "the other game has the boss", boss=boss0)
        slot = next(iter(boss0))
        plays.write(plays.entity(slot), boss0[slot][1] - 7, "<h", 0x3E)  # the fight goes on without them
        for i in range(240):
            run.step(1, p1=("right", "") if plays is a else ("", "right"))
            if i % 30 == 0:
                heal(plays)
        run.expect(plays.snapshot()["world_x"] != x0, f"the partner plays on while the {who} is paused")
        run.expect(bosses(plays), "the boss is still there", boss=bosses(plays))
        run.expect(status(paused)["hp"] == hp, "the paused player can't be hurt", hp=hp, now=status(paused)["hp"])
        close_menu(run, paused)
        run.step(90)
        run.expect(not (paused.mailbox("self_presence").flags & BUSY), "the paused player is back in play")
        pa, pb = a.mailbox("self_presence"), b.mailbox("self_presence")
        run.expect({pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}, "the room is shared again", a=pa.role, b=pb.role)
        run.expect(paused.mailbox("self_presence").role == ROLE_GUEST, "the one who paused is the guest")
        run.expect(sorted(e[1] for e in bosses(a).values()) == sorted(e[1] for e in bosses(b).values()),
                   "both see the boss as it now is", a=bosses(a), b=bosses(b))
        run.expect(len(bosses(paused)) == 1, "one boss", boss=bosses(paused))
        heal(a), heal(b)


@session_scenario(starts=("no1", "entrance"))
def boss_dead_stays_down(run):
    """M5 criterion 5 (D24): A dies in the boss fight and stays down while B fights on; once B
    has beaten the boss, A respawns next to B with full HP."""
    from bots import walker
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    run.step(30)
    a.write("g_Status", 1, "<i", 0x23C)  # one hit from death (harness shortcut)
    bot = walker("right", attack_every=0)
    for i in range(3000):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if i % 20 == 0:
            heal(b)
        if a.mailbox("self_presence").flags & DEAD:
            break
    run.expect(a.mailbox("self_presence").flags & DEAD, "A died in the boss fight", frames=i)
    run.step(400)
    run.expect(a.mailbox("self_presence").flags & DEAD, "A stays down while the boss lives")
    run.expect(b.mailbox("self_presence").flags & BOSS and not b.mailbox("self_presence").flags & DEAD,
               "B fights on")
    for slot in bosses(b):  # B finishes the boss (harness shortcut: one hit left)
        b.write(b.entity(slot), 1, "<h", 0x3E)
    for i in range(1800):
        living = list(bosses(b))
        if not living:
            break
        run.step(1, p1=("", toward(b, b, living[0], i)))
        if i % 20 == 0:
            heal(b)
    run.expect(not bosses(b), "B beat the boss", frames=i)
    t = wait_pulled(run, a, b, 1800)
    st = status(a)
    run.expect(t is not None, "A respawned next to B", frames=t)
    run.expect(st["hp"] == st["hp_max"], "with full HP", hp=st["hp"])


NO0 = 0x00
LEFT_OF_MARIA = (80, 728, 135)  # NO0 room 80 (cells 29-31, row 26), near its right edge


@session_scenario(starts=("no0", "entrance"))
def cutscene_pulls_partner_in(run):
    """M5 criterion 6: A walks into the room where Maria is first met (a cutscene). B is pulled
    into A's room and goes through the scene too; afterwards the shared state matches."""
    from link.mailbox import CUTSCENE
    from session_scenarios import assert_converged
    a, b = run.s.a, run.s.b
    arrive(run, a, NO0, *LEFT_OF_MARIA)
    from bots import walker
    started = None
    bot = walker("right", attack_every=0)
    for i in range(1800):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if a.mailbox("self_presence").flags & CUTSCENE:
            started = i
            break
    run.expect(started is not None, "A's cutscene started", frames=i, stage=hex(a.snapshot()["stage"]))
    pulled = saw = None
    for i in range(1800):
        run.step(1)
        p, q = b.mailbox("self_presence"), a.mailbox("self_presence")
        if pulled is None and p.room == q.room and p.flags & IN_PLAY:
            pulled = i
        if pulled is not None and p.flags & CUTSCENE:
            saw = i
            break
    run.expect(pulled is not None and pulled < 300, "B was pulled into A's room within 5 s", frames=pulled)
    run.expect(saw is not None, "B's game ran the cutscene too", frames=saw)
    for _ in range(3600):  # let both scenes play out
        run.step(1)
        if not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & CUTSCENE:
            break
    run.step(120)
    assert_converged(run)


def aggro_hits(run, control=0):
    """The players stand at opposite ends of the boss room for up to a minute; returns how
    often the boss hurt each."""
    a, b = run.s.a, run.s.b
    a.mailbox("set_control", control)
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    room = a.mailbox("self_presence").room
    for _ in range(120):  # apart, but both stay in the boss room (its exits are open)
        pa = "left" if a.snapshot()["x"] > 40 else ""
        pb = "right" if b.snapshot()["x"] < 216 else ""
        run.step(1, p1=(pa, pb))
    run.expect(a.mailbox("self_presence").room == room == b.mailbox("self_presence").room,
               "both are in the boss room, apart", a=a.snapshot()["world_x"], b=b.snapshot()["world_x"])
    hurt = {"A": 0, "B": 0, "nearer_b": 0, "frames": 0}
    last = {"A": status(a)["hp"], "B": status(b)["hp"]}
    for i in range(3600):
        run.step(1)
        for slot in bosses(a):
            bx = struct.unpack_from("<h", a.read_bytes(a.entity(slot), 0xBC), 2)[0] + a.read("g_Tilemap", "<h", 0xA)
            hurt["nearer_b"] += abs(bx - b.snapshot()["world_x"]) < abs(bx - a.snapshot()["world_x"])
            hurt["frames"] += 1
        for name, g in (("A", a), ("B", b)):
            hp = status(g)["hp"]
            if hp < last[name]:
                hurt[name] += 1
            last[name] = hp
        if i % 10 == 0:
            heal(a), heal(b)
            last = {"A": status(a)["hp"], "B": status(b)["hp"]}
        if not bosses(a):
            break
    return hurt


@session_scenario(starts=("no1", "entrance"))
def boss_aggro_switches(run):
    """M5 criterion 4 (D47): the players stand at opposite ends of the boss room for a minute.
    The boss goes after both of them."""
    hurt = aggro_hits(run)
    switches = run.s.a.mailbox("self_presence").aggro_switches
    run.expect(switches >= 5, "the boss switched targets, again and again", switches=switches)
    run.expect(hurt["A"] > 0 and hurt["B"] > 0, "the boss hit both players", hits=hurt)


@session_scenario(starts=("no1", "entrance"))
def boss_aggro_control(run):
    """The control for boss_aggro_switches: with aggro switched off (CONTROL_NO_AGGRO), the boss
    never switches (so the counter boss_aggro_switches relies on means something). Where the
    boss goes isn't a good measure: the Doppleganger roams the whole (small) room either way."""
    from link.mailbox import CONTROL_NO_AGGRO
    switches0 = run.s.a.mailbox("self_presence").aggro_switches
    hurt = aggro_hits(run, CONTROL_NO_AGGRO)
    switches = run.s.a.mailbox("self_presence").aggro_switches - switches0
    run.expect(switches == 0, "the boss never switched to B", switches=switches, hits=hurt)


@session_scenario(starts=("no1", "entrance"))
def guest_blocked_by_closed_door(run):
    """M5 (and M4): the boss room's door closes in the authority's world; the guest can't walk
    out through it either (the room's tiles come with the snapshot)."""
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    wait_pulled(run, b, a, 300)
    room = a.mailbox("self_presence").room
    for i in range(300):
        run.step(1, p1=("", "right"))
        if i % 20 == 0:
            heal(a), heal(b)
    run.expect(b.mailbox("self_presence").room == room, "B is still in the boss room",
               b=str(b.mailbox("self_presence").room), x=b.snapshot()["x"])


STAGE_MAR = 0x17


def _scene_then_leave(run, together):
    """A meets Maria; B is pulled in; both scenes play; then they leave the clock room, one at a
    time or both at once (playtest 2026-10-20: leaving pulled the other back in, forever)."""
    from link.mailbox import CUTSCENE
    from bots import walker
    a, b = run.s.a, run.s.b
    arrive(run, a, NO0, *LEFT_OF_MARIA)
    bot = walker("right", attack_every=0)
    for i in range(1800):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if a.mailbox("self_presence").flags & CUTSCENE:
            break
    run.expect(a.mailbox("self_presence").flags & CUTSCENE, "A's cutscene started", frames=i)
    began, ended = {}, {}
    for i in range(6000):
        run.step(1)
        for k, g in (("A", a), ("B", b)):
            on = g.mailbox("self_presence").flags & CUTSCENE
            if on and k not in began:
                began[k] = i
            if not on and k in began and k not in ended:
                ended[k] = i
        if len(ended) == 2:
            break
    run.expect(len(began) == 2, "both games ran the scene", began=began)
    run.expect(len(ended) == 2 and abs(ended["A"] - ended["B"]) <= 30,
               "the scenes ended together (within half a second)", ended=ended)
    run.step(60)

    def leave(who, backdash=False):
        pads = {g: walker("left", attack_every=0) for g in who}
        for i in range(1500):
            inp = ["", ""]
            for k, g in enumerate((a, b)):
                if g in pads:
                    inp[k] = pads[g](g.snapshot(), i) + ("+triangle" if backdash and i % 90 < 2 else "")
            run.step(1, p1=tuple(inp))
            if all(g.snapshot()["stage"] == NO0 for g in who) and i > 200:
                break

    def quiet(frames, what):
        scenes = 0
        for _ in range(frames):
            run.step(1)
            scenes += bool((a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & CUTSCENE)
        run.expect(scenes == 0, what, scene_frames=scenes,
                   a=hex(a.snapshot()["stage"]), b=hex(b.snapshot()["stage"]))

    if together:
        leave((a, b), backdash=True)
        run.expect(a.snapshot()["stage"] == b.snapshot()["stage"] == NO0, "both left the clock room together",
                   a=hex(a.snapshot()["stage"]), b=hex(b.snapshot()["stage"]))
        quiet(1200, "no scene starts again afterwards")
    else:
        leave((a,))
        run.expect(a.snapshot()["stage"] == NO0, "A left the clock room", a=hex(a.snapshot()["stage"]),
                   x=a.snapshot()["world_x"])
        quiet(900, "A isn't pulled back, and B's scene doesn't start again")
        run.expect(a.snapshot()["stage"] == NO0 and b.snapshot()["stage"] == STAGE_MAR, "each stays where they are",
                   a=hex(a.snapshot()["stage"]), b=hex(b.snapshot()["stage"]))
        leave((b,))
        run.expect(b.snapshot()["stage"] == NO0, "B left too", b=hex(b.snapshot()["stage"]))
        quiet(900, "still no scene")
    for g in (a, b):
        p = g.mailbox("self_presence")
        run.expect(p.flags & IN_PLAY and not p.flags & DEAD, "both are in play", flags=p.flags)


@session_scenario(starts=("no0", "entrance"))
def cutscene_then_leave_one_by_one(run):
    _scene_then_leave(run, together=False)


@session_scenario(starts=("no0", "entrance"))
def cutscene_then_leave_together(run):
    _scene_then_leave(run, together=True)


@session_scenario(starts=("no1", "entrance"), characters=(0, 1))
def boss_guest_richter_swing_lands_once(run):
    """Issue 157 (0.16.0): Richter's hits in a boss fight, as the guest, landed every frame. He
    swings every 45 frames; the boss's HP (in the authority's world) never drops on frames close
    together."""
    a, b = run.s.a, run.s.b
    into_boss_room(run, a)
    run.expect(wait_pulled(run, b, a, 600) is not None, "Richter is pulled in")
    run.step(60)
    slot = next(iter(bosses(a)))
    hp, drops = bosses(a)[slot][1], []
    for i in range(3600):
        if i % 20 == 0:
            heal(a), heal(b)
        raw = a.read_bytes(a.entity(slot), 0xBC)
        boss_x = struct.unpack_from("<h", raw, 2)[0] + a.read("g_Tilemap", "<h", 0xA)
        me = b.snapshot()["world_x"]
        side = "right" if boss_x > me else "left"
        pad = side if abs(boss_x - me) > 36 else side + "+square" if i % 45 < 2 else ""
        run.step(1, p1=("", pad))
        now = bosses(a).get(slot, (0, 0, 0))[1]
        if now < hp:
            drops.append((i, hp - now))
        hp = now
        if len(drops) >= 8 or slot not in bosses(a) or hp <= 0:
            break
    close = [(x, y) for x, y in zip(drops, drops[1:]) if y[0] - x[0] < 10]
    run.expect(drops, "Richter's swings hit the boss", frames=i)
    run.expect(not close, "each swing lands once: no two hits within 10 frames", drops=drops, close=close)


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
_arena_test("boss_arena_edge_saturn_maria_and_saturn_richter", (4, 5), False)  # #259: their own player code


# --- #259: in the real fight, the possessed Richter's Blade Dash knocked a player back for good ----
LONGEST_HIT = 240  # frames: a fling crosses the arena in well under this


def knockback_lands(run, wide=0, mode="corners"):
    """Both players in the possessed Richter's fight for some 100 s of his attacks, never dying: in
    mode "corners" each stands in a corner of his arena (where the report's player was stuck), in
    "fight" each walks at him and attacks. Each time either is hit, they're out of the hit within
    LONGEST_HIT frames."""
    from session_m12 import SceneWatch
    from link.mailbox import OPT_WIDE_SHIFT
    a, b = run.s.a, run.s.b
    if wide:
        for g in (a, b):
            g.host("set_player", options=wide << OPT_WIDE_SHIFT)
    w = SceneWatch(run)
    boss = lambda g: g.mailbox("self_presence").flags & BOSS
    w.until(lambda: boss(a), 4000, lambda i: ("left" + ("+cross" if i % 90 < 12 else ""),
                                              "left" if b.read("g_CutsceneHasControl") else ""))
    run.expect(boss(a), "A walks into Richter's arena", at=a.snapshot())
    w.until(lambda: boss(b), 3000, ("", "left"))
    run.expect(boss(b), "B is pulled into the fight", b=b.snapshot())
    hit, longest, hits, trail = [0, 0], [(0, None), (0, None)], [0, 0], [[], []]
    for t in range(6000):
        free = not a.read("g_CutsceneHasControl")
        # A to the left corner, B to the right, then they stand there (a jump now and then)
        pads = [("left" if t % 240 < 60 else "") + ("+cross" if t % 400 == 300 else ""),
                ("right" if t % 240 < 60 else "") + ("+cross" if t % 400 == 100 else "")]
        if mode == "fight":  # each walks at him and attacks, jumping now and then, as a player would
            pads = []
            for k, g in enumerate((a, b)):
                foes = [g.read(g.entity(s_), "<h", 2) for s_ in range(64, 96)
                        if g.read(g.entity(s_), "<I", 0x28) and g.read(g.entity(s_), "<h", 0x3E) > 0]
                x = g.read(g.entity(0), "<h", 2)
                d = ("left" if foes and min(foes, key=lambda f: abs(f - x)) < x else "right") if foes else ""
                d = d if not foes or abs(min(foes, key=lambda f: abs(f - x)) - x) > 40 else ""
                pads.append("+".join(p for p in (d, "square" if (t + 7 * k) % 16 < 2 else "",
                                                   "cross" if (t + 50 * k) % 150 < 10 else "") if p))
        run.step(1, (pads[0].strip("+"), pads[1].strip("+")))
        for k, g in enumerate((a, b)):
            if t % 20 == 0:
                g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            p0 = g.entity(0)
            step, step_s, x = g.read(p0, "<H", 0x2C), g.read(p0, "<H", 0x2E), g.read(p0, "<h", 2)
            if not trail[k] or trail[k][-1][1:3] != (step, step_s):
                trail[k] = (trail[k] + [(t, step, step_s, x, g.read(p0, "<h", 6))])[-12:]
            if step == HIT_STEP and free:
                hits[k] += hit[k] == 0
                hit[k] += 1
                if hit[k] > longest[k][0]:
                    longest[k] = (hit[k], list(trail[k]))
            else:
                hit[k] = 0
        if max(h for h, _ in longest) > LONGEST_HIT:
            break
    run.capture()
    run.expect(sum(hits) > 0, "his attacks hit the players", hits=hits)
    for k, who in enumerate("AB"):
        run.expect(longest[k][0] <= LONGEST_HIT, f"{who} is out of every hit within {LONGEST_HIT} frames",
                   hits=hits[k], longest=longest[k][0], trail=longest[k][1], at=(a, b)[k].snapshot())


def _knockback_test(name, characters, wide, full, mode="corners"):
    from session_m12 import STARTS as BOSS_STARTS

    def test(run):
        knockback_lands(run, wide, mode)
    test.__name__ = name
    test.__doc__ = ("Issue 259 (1.0.0): in the Castle Keep, the possessed Richter's Blade Dash knocked a player "
                    "back forever, stuck in a corner. Two players in his corners through 100 s of his attacks: "
                    "every hit ends.")
    start = str(BOSS_STARTS / "Boss - Richter.state")
    session_scenario(starts=(start, start), characters=characters, full=full)(test)


_knockback_test("boss_richter_knockback_lands_alucard_and_richter", (0, 1), 0, False)
_knockback_test("boss_richter_knockback_lands_richter_and_maria", (1, 2), 0, True)
_knockback_test("boss_richter_knockback_lands_alucard_and_alucard", (0, 0), 0, True)
_knockback_test("boss_richter_knockback_lands_alucard_and_maria_21_9", (0, 2), 2, True)
for _c in ((0, 0), (1, 1), (2, 2), (1, 0), (2, 1), (0, 2)):  # players who fight him, as a player would
    for _w in (0, 2):
        _n = "_and_".join(("alucard", "richter", "maria")[c] for c in _c) + ("_21_9" if _w else "")
        _knockback_test(f"boss_richter_knockback_fighting_{_n}", _c, _w, True, "fight")



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


# --- #259 again: pinned in a corner. He walks onto a player in a corner and stands there (his own
# AI: alone too), hitting them each time their invincibility ends. A player gets out from under him.
PINNED_NEAR = 20     # px: he's on the player
ESCAPE_FRAMES = 600  # to get 64 px out of the corner


def corner_escape(run, who):
    """Both in the possessed Richter's fight, `who` (0: A, 1: B) in the left corner and the other in
    the right, until he stands on `who` there and hits them; then `who` plays as someone escaping
    would: away from the wall, jumping whenever they can. They're out within ESCAPE_FRAMES."""
    from session_m12 import SceneWatch
    a, b = run.s.a, run.s.b
    g = (a, b)[who]
    w = SceneWatch(run)
    boss = lambda h: h.mailbox("self_presence").flags & BOSS
    w.until(lambda: boss(a), 4000, lambda i: ("left" + ("+cross" if i % 90 < 12 else ""),
                                              "left" if b.read("g_CutsceneHasControl") else ""))
    w.until(lambda: boss(b), 3000, ("", "left"))
    run.expect(boss(a) and boss(b), "both are in Richter's fight", a=a.snapshot(), b=b.snapshot())
    p0, rich = g.entity(0), g.entity(64)
    pinned = None
    for t in range(9000):
        sides = ["left", "right"] if who == 0 else ["right", "left"]
        run.step(1, tuple(sd if t % 240 < 60 else "" for sd in sides))
        for h in (a, b):
            if t % 20 == 0:
                h.write("g_Status", h.read("g_Status", "<i", 0x240), "<i", 0x23C)
        x, bx = g.read(p0, "<h", 2), g.read(rich, "<h", 2)
        if x < 24 and abs(bx - x) < PINNED_NEAR and g.read(p0, "<H", 0x2C) == HIT_STEP:
            pinned = t
            break
    run.expect(pinned is not None, "he pins the player in the corner", at=g.snapshot())
    pads, trail, out = ["", ""], [], None
    for t in range(ESCAPE_FRAMES):
        step = g.read(p0, "<H", 0x2C)
        pads[who] = "right" + ("+cross" if t % 24 < 12 else "")
        run.step(1, tuple(pads))
        for h in (a, b):
            if t % 20 == 0:
                h.write("g_Status", h.read("g_Status", "<i", 0x240), "<i", 0x23C)
        x, y = g.read(p0, "<h", 2), g.read(p0, "<h", 6)
        if not trail or trail[-1][1:3] != (step, g.read(p0, "<H", 0x2E)):
            trail = (trail + [(t, step, g.read(p0, "<H", 0x2E), x, y, g.read(rich, "<h", 2), g.read(rich, "<H", 0x2C))])[-20:]
        if x > 64:
            out = t
            break
    run.capture()
    run.expect(out is not None, f"out of the corner within {ESCAPE_FRAMES} frames ({out})", trail=trail, at=g.snapshot())


def _escape_test(name, characters, who, full):
    from session_m12 import STARTS as BOSS_STARTS

    def test(run):
        corner_escape(run, who)
    test.__name__ = name
    test.__doc__ = ("Issue 259: the possessed Richter stands on a player in a corner and hits them as soon as "
                    "their invincibility ends. A player escaping (away, jumping) gets out of the corner.")
    start = str(BOSS_STARTS / "Boss - Richter.state")
    session_scenario(starts=(start, start), characters=characters, full=full)(test)


_escape_test("boss_richter_corner_escape_alucard", (0, 1), 0, False)
_escape_test("boss_richter_corner_escape_richter", (1, 0), 0, False)
_escape_test("boss_richter_corner_escape_maria", (2, 0), 0, True)
_escape_test("boss_richter_corner_escape_richter_partner", (0, 1), 1, True)
