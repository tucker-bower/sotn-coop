"""M12 session tests (design/M12-coverage.md): cutscenes together, starting with the prologue
(playtest 2026-10-25 note 1: the Richter vs Dracula prologue didn't sync the players for its
scenes, nor for the scene after it)."""

from coop_env import TOOLS
from session import session_scenario

ST0, NO3 = 0x1F, 0x41
FLAG_DEAD = 0x100  # include/game.h
# The prologue's stairs up to the throne room: hold up+left until the opening scene starts.
CLIMB = "up+left"


class SceneWatch:
    """Each game's cutscene edges (g_CutsceneHasControl), in session frames."""

    def __init__(self, run):
        self.run, self.t = run, 0
        self.on = [False, False]
        self.starts, self.ends = [[], []], [[], []]
        self.log = [[], []]
        self.shots = {}  # frame -> label: both screens are saved then (scene starts, and 15 frames on)  # each game's last state changes: (frame, cutscene, stage, room, presence flags)

    def step(self, n, pads=("", "")):
        def each(i, sa, sb):
            self.t += 1
            for k, g in enumerate((self.run.s.a, self.run.s.b)):
                cs = bool(g.read("g_CutsceneHasControl"))
                key = (int(cs), g.read("g_StageId"), g.snapshot()["room"], g.mailbox("self_presence").flags,
                       g.read("g_Status", "<I", EQUIPMENT_OFS))
                if not self.log[k] or self.log[k][-1][1:] != key:
                    self.log[k] = (self.log[k] + [(self.t, *key)])[-12:]
                if cs and not self.on[k]:
                    self.starts[k].append(self.t)
                    if len(self.starts[k]) <= 3:
                        self.shots[self.t + 1] = f"start{'ab'[k]}{len(self.starts[k])}"
                        self.shots[self.t + 15] = f"start{'ab'[k]}{len(self.starts[k])}+15"
                        self.shots[self.t + 900] = f"start{'ab'[k]}{len(self.starts[k])}+900"
                elif self.on[k] and not cs:
                    self.ends[k].append(self.t)
                self.on[k] = cs
            if self.t in self.shots:
                out = TOOLS["out"] / self.run.name
                out.mkdir(parents=True, exist_ok=True)
                for g, ab in ((self.run.s.a, "a"), (self.run.s.b, "b")):
                    g.screenshot().save(out / f"{self.t:06d}_{self.shots[self.t]}_{ab}.png")
        self.run.step(n, pads, each)

    def until(self, cond, limit, pads=("", "")):
        """pads: a pair, or a function of the frame giving one."""
        for i in range(limit):
            if cond():
                return True
            self.step(1, pads(i) if callable(pads) else pads)
        return cond()


def control_back(run, w, pad="right", limit=600, axis="world_x"):
    """After a scene: the frame each player first moves under the pad (control is back)."""
    x0 = [g.snapshot()[axis] for g in (run.s.a, run.s.b)]
    moved = [None, None]
    for i in range(limit):
        p = pad(i) if callable(pad) else pad
        w.step(1, (p, p))
        for k, g in enumerate((run.s.a, run.s.b)):
            if moved[k] is None and g.snapshot()[axis] != x0[k]:
                moved[k] = w.t
        if None not in moved:
            break
    return moved


def stage(g):
    return g.read("g_StageId")


@session_scenario(starts=("st0_start", "st0_start"))
def m12_prologue_opening(run):
    """Both players see the prologue's opening scene (Richter meets Dracula) together, though B
    starts 5 s behind A (as online, where one skips the video sooner)."""
    w = SceneWatch(run)
    for _ in range(300):  # A runs ahead alone
        run.s.a.step(1, CLIMB)
    w.until(lambda: w.starts[0] and w.starts[1], 3000, (CLIMB, CLIMB))
    run.expect(w.starts[0] and w.starts[1], "both games start the opening scene", starts=w.starts)
    # The scene starts near the top of the stairs: the game steers Richter once he's off them, so
    # each player keeps climbing (EntityCutsceneSupport waits for a standing or walking player).
    w.step(600, (CLIMB, CLIMB))
    w.until(lambda: w.ends[0] and w.ends[1], 4200)
    run.expect(w.ends[0] and w.ends[1], "both end it", ends=w.ends, starts=w.starts, t=w.t,
               cs=[g.read("g_CutsceneHasControl") for g in (run.s.a, run.s.b)],
               at=[g.snapshot() for g in (run.s.a, run.s.b)])
    moved = control_back(run, w)
    run.expect(None not in moved and abs(moved[0] - moved[1]) <= 3,
               "both players get control back within 3 frames of each other", moved=moved, ends=w.ends)
    run.expect(len(w.starts[0]) == len(w.starts[1]) == 1, "the scene played once each", starts=w.starts)


def enemies(g):
    """{slot: (id, world x, world y, hp)} of this game's living, hittable stage entities."""
    from session_shared import stage_entities
    return {k: v[:4] for k, v in stage_entities(g).items() if 0 < v[3] < 32767}


def fight_pad(g, period=12, t=0):
    """A plain fight bot: walk to the nearest enemy, face it, whip (□) on a rhythm, jump now and then."""
    snap = g.snapshot()
    foes = enemies(g)
    if not foes:
        return ""
    x, y = snap["world_x"], snap["world_y"]
    _, ex, ey, _ = min(foes.values(), key=lambda v: abs(v[1] - x) + abs(v[2] - y))
    way = "right" if ex > x else "left"
    pad = way if abs(ex - x) > 40 else ""
    if t % period < 2:
        pad = (way + "+square") if not pad else pad + "+square"
    if ey < y - 40 and t % 60 < 20:
        pad = (pad + "+cross") if pad else "cross"
    return pad


@session_scenario(starts=("st0_fight", "st0_fight"))
def m12_prologue_fight(run):
    """One Dracula for both (a shared room): when he falls, the scenes after the fight play in
    both games together, and both leave the prologue for the castle together."""
    a, b = run.s.a, run.s.b
    w = SceneWatch(run)
    roles = set()
    left, how = [None, None], [None, None]
    (TOOLS["out"] / run.name).mkdir(parents=True, exist_ok=True)
    for t in range(30000):
        roles.add((a.mailbox("self_presence").role, b.mailbox("self_presence").role))
        if t % 30 == 0:  # the test is about the flow, not the fight: Dracula is worn down fast
            for slot, (eid, _, _, hp) in enemies(a).items():
                if hp > 8:
                    a.write("g_Entities", 8, "<h", slot * 0xBC + 0x3E)
        w.step(1, (fight_pad(a, t=t), fight_pad(b, t=t + 6)))
        for k, g in enumerate((a, b)):
            if left[k] is None and (g.read("g_StageId") != ST0 or g.read("g_GameState") != 2):
                left[k] = w.t
                how[k] = (g.read("g_GameState"), g.read("g_StageId"), g.snapshot()["hp"])
                g.screenshot().save(TOOLS["out"] / run.name / f"left_{'ab'[k]}.png")
        if None not in left:
            break
    run.expect((1, 2) in roles or (2, 1) in roles, "the throne room is a shared room (one Dracula)", roles=sorted(roles))
    run.expect(None not in left, "both games leave the prologue", left=left, how=how, starts=w.starts, ends=w.ends)
    run.expect(abs(left[0] - left[1]) <= 120, "within 2 s of each other", left=left)
    run.expect(len(w.starts[0]) == len(w.starts[1]), "the same scenes in both games",
               starts=w.starts, ends=w.ends)
    for (s0, s1) in zip(w.starts[0], w.starts[1]):
        run.expect(abs(s0 - s1) <= 30, "each scene starts in both within half a second", starts=w.starts)


DEATH_ROOM = (20, 39)  # NO3: E_CUTSCENE runs the Death scene (savestates.py)
EQUIPMENT_OFS = 0x29C  # g_Status.equipment[0]


def walk_to_death(run, w, g, other_pad=""):
    """savestates.play_to_death in a session: hold right and jump on a rhythm until Death's room,
    trying rhythms from a state until one gets there (some drop into a dead end)."""
    pads = lambda p: (p, other_pad) if g is run.s.a else (other_pad, p)
    w.step(600, pads(""))
    w.step(3000, pads("right"))
    start = g.save_state()
    for period in (40, 36, 44, 32, 48, 28, 52, 56, 60):
        g.load_state(start)
        for i in range(8000):
            room = g.snapshot()["room"]
            if room in (DEATH_ROOM, (14, 41)) or g.read("g_CutsceneHasControl"):
                break
            w.step(1, pads("right+cross" if i % period < period // 2 else "right"))
        if room != (14, 41):
            return True
    return False


@session_scenario(starts=("no3_start", "st0_end"))
def m12_death_waits_for_partner(run):
    """Playtest 2026-10-25: whoever finished the prologue first watched Death take Alucard's gear
    alone. Now the scene waits (up to 60 s) for a partner still in the prologue's ending, who is
    then pulled in; both watch it together and both lose their gear."""
    a, b = run.s.a, run.s.b
    w = SceneWatch(run)
    run.expect(walk_to_death(run, w, a), "A reaches Death's room")
    # B skips through the prologue's ending (Start), and stops pressing once in the castle
    skip = lambda i: ("right", "start" if b.read("g_GameState") != 2 and i % 120 < 2 else "")
    w.until(lambda: w.starts[0] and w.starts[1], 5000, skip)
    run.expect(w.starts[0] and w.starts[1], "both games play Death's scene", starts=w.starts,
               b=(b.read("g_GameState"), b.read("g_StageId"), b.snapshot()["room"]))
    w.until(lambda: w.ends[0] and w.ends[1], 4000)
    run.expect(w.ends[0] and w.ends[1], "both end it", ends=w.ends)
    w.step(400)  # Death takes the gear about a second after the dialogue, then leaves
    gear = [g.read("g_Status", "<I", EQUIPMENT_OFS) for g in (a, b)]
    run.expect(gear == [0, 0], "Death took both Alucards' gear", gear=gear, log=w.log)
    moved = control_back(run, w, lambda i: "cross" if i % 4 < 2 else "", axis="world_y")  # jumps: walls don't matter
    run.expect(None not in moved and abs(moved[0] - moved[1]) <= 3,
               "both players get control back within 3 frames of each other", moved=moved, ends=w.ends,
               starts=w.starts, log=w.log)


# --- the cutscene catalogue (design/M12 part 1) ----------------------------------------------
# name: (A's start: a fixture or a debug start, A's pad to walk into the scene, frames allowed).
# B starts at the castle entrance: it's pulled in, and both must play the scene together.
STARTS = TOOLS["out"].parent / "fixtures" / "debug-starts"
SCENES = {
    "succubus": (STARTS / "Boss - Succubus.state", "right", 6000),
    "richter_castle_keep": (STARTS / "Boss - Richter.state", "left", 6000),
}


DECOMP = TOOLS["out"].parent / "src" / "sotn-decomp"
STAGE_IDS = {"nz0": 0x0C, "lib": 0x02, "dai": 0x06, "cen": 0x08, "top": 0x0B, "dre": 0x12}
# Scenes reached by sending A to the scene's room (its entity's layout in the decomp's
# assets/st/<stage>/entity_layouts.json), from the debug start nearest before it in the story.
# name: (base start, stage, entity layout, entity x, y, which side A comes from, the castle flag
# that marks the scene seen: include/castle_flags.h; it's cleared in both games first)
ROOM_SCENES = {
    "maria_alchemy_lab": ("Alchemy Laboratory", "nz0", 15, 128, 128, "left", 0x85),  # MET_MARIA_IN_NZ0
    "castle_keep": ("Boss - Cerberus", "top", 1, 896, 896, "left", None),
}
# From the scene starts (launcher/bossstarts.S: the room before the scene, that point's progress):
# both games load it, A walks in, B is pulled in.
START_SCENES = {
    "maria_chapel_from_start": ("Scene - Maria in the Royal Chapel", "left"),
    "maria_alchemy_lab_from_start": ("Scene - Maria in the Alchemy Lab", "left"),  # from the right: her scene steers Alucard left
    "castle_keep_from_start": ("Scene - The Castle Keep", "right"),
}
# Not yet triggered by the harness (docs/STATUS.md), so not registered:
OPEN_SCENES = {
    # talking to him (Up next to his chair) didn't start it yet
    "librarian": ("Boss - Doppleganger10", "lib", 2, 80, 172, "right", 0x72),       # MET_LIBRARIAN
    # started once on arrival, then not when both games share the start: what else it needs is open
    "maria_chapel": ("Boss - Minotaur and Werewolf", "dai", 4, 256, 128, "left", 0x63),  # MET_MARIA_IN_DAI
    # starts as soon as one enters the room and steers Alucard to Maria: the harness's arrival
    # spots (and the scene start's) are on the wrong floor; idle, Alucard drops to the floor below
    # and the scene never ends, even in one game
    "maria_center": ("Boss - Granfaloon", "cen", 1, 384, 544, "left", 0xD8),       # MET_MARIA_IN_CEN
}


def scene_room(stage, layout):
    """(room id: its offset in the stage's room table, its map cell) of the room using this entity
    layout."""
    import json
    lists = json.loads((DECOMP / "assets" / "st" / stage / "entity_layouts.json").read_text())["indices"]
    rooms = json.loads((DECOMP / "assets" / "st" / stage / "rooms.json").read_text())
    for i, r in enumerate(rooms):  # a room's entityLayoutId picks an entity list through "indices"
        if lists[r["entityLayoutId"]] == layout:
            return i * 8, (r["left"], r["top"])
    raise KeyError((stage, layout))


def arrive_in(run, g, stage, room, cell, x, y, limit=900):
    """Sends g there; done once it's in play in that map cell (a scene may start at once)."""
    from link.mailbox import CMD_ARRIVE, IN_PLAY
    g.mailbox("command", CMD_ARRIVE, stage, room, x, y)
    for _ in range(limit):
        run.step(1)
        p = g.mailbox("self_presence")
        if p.stage == stage and (p.room_left, p.room_top) == cell and p.flags & IN_PLAY:
            return True
    run.expect(False, f"A arrives in room {cell} of stage {stage:#x}", presence=str(p))


def scene_together(run, pad, limit, flags0=None):
    """A walks (pad) until its scene starts; B, elsewhere, is pulled in. Both play it once, and
    both get control back together; the castle flags match after."""
    a, b = run.s.a, run.s.b
    w = SceneWatch(run)
    w.flags0 = flags0 or [g.read_bytes("g_CastleFlags", 0x300) for g in (a, b)]
    if a.read("g_CutsceneHasControl"):  # it started as A arrived
        w.on[0], w.starts[0] = True, [0]
    w.until(lambda: w.starts[0], limit, pad if callable(pad) else (pad, ""))
    run.expect(w.starts[0], "A's scene starts", at=a.snapshot())
    # B, pulled in, walks on as a player would: some scenes start on crossing a spot (Maria in the
    # Center), not on arriving at it
    walk = pad if isinstance(pad, str) else ""
    w.until(lambda: w.starts[1], 1200, ("", walk))
    run.expect(w.starts[1], "B is pulled in and plays it too", starts=w.starts, log=w.log)
    w.until(lambda: len(w.ends[0]) >= len(w.starts[0]) and len(w.ends[1]) >= len(w.starts[1])
            and not any(w.on), 12000)  # no input: the dialogue moves on by itself (a jump left a scene unseen)
    run.expect(not any(w.on), "both end it", ends=w.ends, starts=w.starts)
    w.step(120)
    run.expect(len(w.starts[0]) == 1 and len(w.starts[1]) == 1, "once each", starts=w.starts, log=w.log)
    flags = [g.read_bytes("g_CastleFlags", 0x300) for g in (a, b)]
    # what either game's scene changed, the other has too
    diff = [i for i in range(0x300) if (flags[0][i] != w.flags0[0][i] or flags[1][i] != w.flags0[1][i])
            and flags[0][i] != flags[1][i]]
    run.expect(not diff, "the castle flags the scene set match", diff=diff[:10])


def _scene_test(name, start, pad, limit):
    def test(run):
        scene_together(run, pad, limit)
    test.__name__ = f"m12_scene_{name}"
    test.__doc__ = f"Cutscene catalogue: {name.replace('_', ' ')}, played together."
    session_scenario(starts=(str(start), "entrance"))(test)


for _name, (_start, _pad, _limit) in SCENES.items():
    _scene_test(_name, _start, _pad, _limit)


def _room_scene_test(name, base, stage, layout, x, y, side, flag):
    def test(run):
        if flag is not None:
            for g in (run.s.a, run.s.b):
                g.write("g_CastleFlags", 0, "<B", flag)
        flags0 = [g.read_bytes("g_CastleFlags", 0x300) for g in (run.s.a, run.s.b)]
        room, cell = scene_room(stage, layout)
        ax = x - 72 if side == "left" else x + 72
        arrive_in(run, run.s.a, STAGE_IDS[stage], room, cell, max(ax, 8), y)
        walk = "right" if side == "left" else "left"
        pad = (lambda i: (walk if i < 60 else ("up" if i % 20 < 2 else ""), "")) if name == "librarian" else walk
        scene_together(run, pad, 1800, flags0)
    test.__name__ = f"m12_scene_{name}"
    test.__doc__ = f"Cutscene catalogue: {name.replace('_', ' ')}, played together."
    # both from the same progress (their shared flags), B elsewhere in it: B is pulled in
    session_scenario(starts=(str(STARTS / f"{base}.state"),) * 2)(test)


for _name, _args in ROOM_SCENES.items():
    _room_scene_test(_name, *_args)


# --- every boss (design/M12 part 2) -----------------------------------------------------------
def _bossstarts():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
    import bossstarts
    return bossstarts.B


def boss_flow(run, b, limit=24000):
    """A walks into the boss; B, at the door, is pulled in; the boss has twice its HP; both fight it
    (worn down: this tests the flow, not the fight); it falls once, both are fine after, and what
    the fight set in the castle flags is the same in both."""
    from link.mailbox import BOSS, DEAD, IN_PLAY, ROLE_AUTHORITY
    a, g2 = run.s.a, run.s.b
    flags0 = [g.read_bytes("g_CastleFlags", 0x300) for g in (a, g2)]
    w = SceneWatch(run)
    walk = b["walk"]
    boss = lambda g: g.mailbox("self_presence").flags & BOSS
    if b.get("check"):  # the way in needs something a bot can't do (mist through bars): start past it
        from session_progress import arrive
        room, x, y = b["check"]
        for g in (a, g2):
            arrive(run, g, a.mailbox("self_presence").stage, room, x, y)
    # B walks too, as a player would (some arenas open with a scene that only moves on while the
    # player holds a direction); it stays where it is otherwise (the door's edge)
    w.until(lambda: boss(a), 4000, lambda i: (walk + ("+cross" if i % 90 < 12 else ""),
                                              walk if g2.read("g_CutsceneHasControl") else ""))
    run.expect(boss(a), "A walks into the boss's room", at=a.snapshot())
    # a pulled-in partner may first play the arena's scene (Minotaur & Werewolf), which steers it
    # only while a direction is held (like the prologue's)
    w.until(lambda: boss(g2), 3000, ("", walk))
    run.expect(boss(g2), "B is pulled into the fight", b=g2.snapshot())
    hp_seen = {}
    fought = 0
    role_log = []
    for t in range(limit):
        pa, pb = a.mailbox("self_presence"), g2.mailbox("self_presence")
        if not role_log or role_log[-1][1:] != (pa.role, pb.role, pa.flags, pb.flags):
            role_log = (role_log + [(t, pa.role, pb.role, pa.flags, pb.flags)])[-14:]
        auth = a if pa.role == ROLE_AUTHORITY else g2
        if t % 30 == 0:
            for g in (a, g2):  # the players don't die: this tests the flow, not the bot's fighting
                g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            for slot, (eid, _, _, hp) in enemies(auth).items():
                hp_seen.setdefault(slot, hp)
                if hp > 8:
                    auth.write("g_Entities", 8, "<h", slot * 0xBC + 0x3E)
                elif t > 3000:  # the bot can't land the last hit (flying bosses): a scripted kill,
                    # as the game's hit detection does when HP runs out (design/M12 part 2)
                    auth.write("g_Entities", 0, "<h", slot * 0xBC + 0x3E)
                    flags = auth.read("g_Entities", "<I", slot * 0xBC + 0x34)
                    auth.write("g_Entities", flags | FLAG_DEAD, "<I", slot * 0xBC + 0x34)
        w.step(1, (fight_pad(a, t=t), fight_pad(g2, t=t + 6)))
        fought = 0 if (boss(a) or boss(g2)) else fought + 1
        if fought > 300:
            break
    run.expect(fought > 300, "the boss falls: no fight in either game", hp_first=sorted(hp_seen.values())[-3:],
               boss=[bool(boss(g)) for g in (a, g2)], roles=[g.mailbox("self_presence").role for g in (a, g2)],
               left=[sorted((v[0], v[3]) for v in enemies(g).values())[:6] for g in (a, g2)],
               cs=[g.read("g_CutsceneHasControl") for g in (a, g2)], role_log=role_log)
    w.step(300)
    for g, n in ((a, "A"), (g2, "B")):
        p = g.mailbox("self_presence")
        run.expect(p.flags & IN_PLAY and not p.flags & DEAD, f"{n} is in play and alive after", flags=p.flags)
    flags = [g.read_bytes("g_CastleFlags", 0x300) for g in (a, g2)]
    diff = [i for i in range(0x300) if (flags[0][i] != flags0[0][i] or flags[1][i] != flags0[1][i])
            and flags[0][i] != flags[1][i]]
    run.expect(not diff, "what the fight set in the castle flags is the same in both", diff=diff[:10])


def _boss_test(b):
    name = b["name"].replace(" & ", " and ")
    def test(run):
        boss_flow(run, b)
    test.__name__ = "m12_boss_" + name.lower().replace(" ", "_")
    test.__doc__ = f"Every boss, together: {b['name']} ({b['area']})."
    start = str(STARTS / f"Boss - {name}.state")
    session_scenario(starts=(start, start))(test)


for _b in _bossstarts():
    _boss_test(_b)


# --- the partner's attacks on screen (playtest 2026-10-25 note 2, sprites.c) ------------------
SUBWEAPON_ID, HEARTS_ADDR, DAGGER = 0x80097BFC, 0x80097BA8, 1


@session_scenario(characters=(1, 1))  # CHAR_RICHTER twice: his whip's sprites are in both games
def m12_partner_attack_drawn(run):
    """Note 2, phase 1: A (Richter) whips next to B (Richter): B gets A's sprites and draws them (the
    same frame of B, from the same state, rendered with and without them differs). DRA's
    subweapons draw with primitives, not sprites: phase 1b."""
    from session_m8 import as_characters
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    as_characters(run, 1, 1)
    into_hall(run)
    got = None
    for i in range(240):
        run.step(1, ("square" if i % 30 < 2 else "", ""))
        n = b.mailbox("partner_sprite_count")
        if n:
            got = n
            break
    run.expect(got, "B receives A's sprites (the whip)")
    run.step(2, ("square", ""))  # a fresh crack...
    run.step(8)                  # ...held out (the whip's segments are blank when it's in)
    b.unlink()  # B's host stops writing: the test sets B's partner sprites itself
    n = b.mailbox("partner_sprite_count")
    sprites = a.mailbox("self_sprites")
    state = b.save_state()  # holds the 15 sprites
    b.mailbox("write_partner_sprites", b"")
    run.s.b.step(10)  # the screen shows a frame a few frames late
    shot_without = b.screenshot()
    without = shot_without.tobytes()
    b.load_state(state)
    run.s.b.step(10)
    from module import symbols
    placed_with = (b.read(symbols()["g_CoopSpritesDrawn"], "<I"), b.read(symbols()["g_CoopSpritesWhy"], "<I"))
    shot_with = b.screenshot()
    with_sprites = shot_with.tobytes()
    out = TOOLS["out"] / run.name
    out.mkdir(parents=True, exist_ok=True)
    shot_with.save(out / "b_with.png")
    shot_without.save(out / "b_without.png")
    a.screenshot().save(out / "a.png")
    from module import symbols
    run.expect(with_sprites != without, "B draws them", sprites=n,
               placed_with=placed_with,
               partner_char=b.mailbox("partner_presence").character, mine=b.mailbox("self_presence").character,
               sets=sorted({hex(int.from_bytes(sprites[k:k + 2], "little")) for k in range(0, len(sprites), 0x14)}))


@session_scenario()
def m12_partner_dagger_drawn(run):
    """Note 2, phase 1b: A (Alucard) throws daggers next to B: B gets the dagger's primitives and
    draws them (the same frame of B, from the same state, with and without them, differs)."""
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    into_hall(run)
    got = 0
    for i in range(240):
        a.write(SUBWEAPON_ID, DAGGER, "<i")
        a.write(HEARTS_ADDR, 99, "<i")
        run.step(1, ("up+square" if i % 30 < 2 else "", ""))
        if i % 30 == 8 and a.mailbox("self_prims"):
            got = len(a.mailbox("self_prims")) // 0x30
            break
    run.expect(got, "A's dagger has primitives to send", n=got)
    run.step(1)
    b.unlink()
    state = b.save_state()  # holds A's primitives
    b.mailbox("write_partner_prims", b"")
    run.s.b.step(10)  # the screen shows a frame a few frames late
    without = b.screenshot()
    from emu import SYMBOLS
    buf = b.read_bytes(SYMBOLS["g_PrimBuf"], 0x34 * 0x500)
    marked = [(k, buf[k * 0x34 + 7], hex(int.from_bytes(buf[k * 0x34 + 0x32:k * 0x34 + 0x34], "little")))
              for k in range(0x500) if buf[k * 0x34 + 0x2B] == 0xC5]
    pool_without = (len(marked), sum(1 for m in marked if not int(m[2], 16) & 8), marked[:3])
    b.load_state(state)
    run.s.b.step(10)
    with_prims = b.screenshot()
    out = TOOLS["out"] / run.name
    out.mkdir(parents=True, exist_ok=True)
    with_prims.save(out / "b_with.png")
    without.save(out / "b_without.png")
    import struct
    raw = b.read_bytes("g_Entities", 0xBC * 64)
    b_own = [(k, hex(struct.unpack_from("<H", raw, k * 0xBC + 0x26)[0])) for k in range(1, 64)
             if struct.unpack_from("<H", raw, k * 0xBC + 0x26)[0]]
    run.expect(with_prims.tobytes() != without.tobytes(), "B draws them", prims=got, b_entities=b_own,
               b_pad_sub=b.read(SUBWEAPON_ID, "<i"), pool_without=pool_without)


# --- every boss with other characters (design/M12 part 2: R+M and A+R) ------------------------
PAIRINGS = {"rm": (1, 2), "ar": (0, 1)}  # CHAR_* of A and B


def _boss_pair_test(b, tag, chars):
    name = b["name"].replace(" & ", " and ")

    def test(run):
        import sys
        from pathlib import Path
        from session_m8 import as_characters
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
        import bossstarts
        from link.mailbox import CMD_ARRIVE
        as_characters(run, *chars)
        # the load puts them back at the save's room, not at the boss's door: back to the start's spot
        stage = bossstarts.STAGES[b["stage"]]
        room, x, y = b["arrive"]
        for g in (run.s.a, run.s.b):
            g.mailbox("command", CMD_ARRIVE, stage, room, x, y)
        run.step(240)
        boss_flow(run, b)
    test.__name__ = f"m12_boss_{tag}_" + name.lower().replace(" ", "_")
    test.__doc__ = f"{b['name']} together, as {tag.upper()} (Alucard, Richter, Maria)."
    start = str(STARTS / f"Boss - {name}.state")
    session_scenario(starts=(start, start), characters=chars)(test)


for _b in _bossstarts():
    if _b["name"] == "Succubus":  # the Nightmare: no saving there, so no character change at her door
        continue
    for _tag, _chars in PAIRINGS.items():
        _boss_pair_test(_b, _tag, _chars)


def _start_scene_test(name, start, walk):
    def test(run):
        scene_together(run, walk, 3000)
    test.__name__ = f"m12_scene_{name}"
    test.__doc__ = f"Cutscene catalogue, from its scene start: {start}."
    path = str(STARTS / f"{start}.state")
    session_scenario(starts=(path, path))(test)


for _name, (_start, _walk) in START_SCENES.items():
    _start_scene_test(_name, _start, _walk)


# --- doors in a shared room (D107) ----------------------------------------------------------
@session_scenario(starts=("no1", "no1"))
def m12_guest_opens_red_door(run):
    """D107: in a shared room, the guest opens a red door itself and walks out through it (it
    used to get the authority's closed door, and was walled in until the authority went through).
    The Outer Wall's first room, with a red door at its left edge."""
    from link.mailbox import ROLE_AUTHORITY, ROLE_GUEST
    a, b = run.s.a, run.s.b
    run.step(60)
    roles = (a.mailbox("self_presence").role, b.mailbox("self_presence").role)
    run.expect(roles == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B its guest", roles=roles)
    room = b.snapshot()["room"]
    for t in range(400):
        run.step(1, ("", "left"))
        if b.snapshot()["room"] != room:
            break
    run.expect(b.snapshot()["room"] != room, "B walks out through the door", at=b.snapshot(), frames=t)
    run.expect(a.snapshot()["room"] == room, "A stays", at=a.snapshot())


# --- the partner's hand-weapon swings (note 2, phase 2: weapons.c) ---------------------------
def _swing_drawn(run, chars, button, item_index=0):
    """A swings a hand weapon next to B: B gets the weapon's copy (overlay, sheet, palettes)
    through the link, and draws the swing (the same frame of B, from the same state, with and
    without A's sprites, differs; and B drew weapon sprites)."""
    from link.mailbox import WEAPON_MAGIC, WEAPON_PARTNER
    from module import symbols
    from scenarios_m12 import (CATEGORY_OFS, EQUIP_DEFS, EQUIP_SIZE, N_HAND_ITEMS, WEAPON_CATEGORIES)
    from scenarios_m8 import EQUIPMENT
    from session_m8 import as_characters
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    raw = a.read_bytes(EQUIP_DEFS, EQUIP_SIZE * N_HAND_ITEMS)
    items = [i for i in range(1, N_HAND_ITEMS) if raw[i * EQUIP_SIZE + CATEGORY_OFS] in WEAPON_CATEGORIES]
    hand = 0  # the right hand (○ swings it for Richter and Maria, as in the hand-item tests)
    a.write(EQUIPMENT, items[item_index], "<I")
    as_characters(run, *chars)  # the load loads the weapon
    into_hall(run)
    got = False
    for _ in range(300):
        run.step(1)
        if b.read(WEAPON_PARTNER + hand * 0x8000, "<I") == WEAPON_MAGIC:
            got = True
            break
    run.expect(got, "B has A's weapon (its copy came through the link)", item=items[item_index],
               a_seq=a.mailbox("self_weapon_seq", hand))
    drawn_at = None
    drawn_sym = symbols()["g_CoopWeaponsDrawn"]
    for i in range(240):
        run.step(1, (button if i % 40 < 2 else "", ""))
        if b.read(drawn_sym, "<I"):
            drawn_at = i
            break
    run.expect(drawn_at is not None, "B draws A's swing", sprites=b.mailbox("partner_sprite_count"))
    b.unlink()  # B's host stops writing: the test sets B's partner sprites itself
    state = b.save_state()
    b.mailbox("write_partner_sprites", b"")
    run.s.b.step(10)  # the screen shows a frame a few frames late
    without = b.screenshot()
    b.load_state(state)
    run.s.b.step(10)
    with_swing = b.screenshot()
    out = TOOLS["out"] / run.name
    out.mkdir(parents=True, exist_ok=True)
    with_swing.save(out / "b_with.png")
    without.save(out / "b_without.png")
    a.screenshot().save(out / "a.png")
    run.expect(with_swing.tobytes() != without.tobytes(), "the swing is on B's screen")


@session_scenario()
def m12_partner_swing_drawn(run):
    """Note 2, phase 2: Alucard swings a sword next to Alucard."""
    _swing_drawn(run, (0, 0), "square")


@session_scenario(characters=(1, 0))
def m12_partner_swing_drawn_richter(run):
    """Note 2, phase 2: Richter swings his off-hand sword (D105) next to Alucard."""
    _swing_drawn(run, (1, 0), "circle")
