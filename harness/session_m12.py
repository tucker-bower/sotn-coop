"""M12 session tests (design/M12-coverage.md): cutscenes together, starting with the prologue
(playtest 2026-10-25 note 1: the Richter vs Dracula prologue didn't sync the players for its
scenes, nor for the scene after it)."""

from coop_env import TOOLS
from session import session_scenario

ST0, NO3 = 0x1F, 0x41
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
    "librarian": ("Boss - Doppleganger10", "lib", 2, 80, 172, "right", 0x72),       # MET_LIBRARIAN: talk (Up)
    "maria_chapel": ("Boss - Minotaur and Werewolf", "dai", 4, 256, 128, "left", 0x63),  # MET_MARIA_IN_DAI
    "maria_center": ("Boss - Granfaloon", "cen", 1, 384, 544, "left", 0xD8),       # MET_MARIA_IN_CEN
    "castle_keep": ("Boss - Cerberus", "top", 1, 896, 896, "left", None),
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
    w.until(lambda: w.starts[1], 1200)
    run.expect(w.starts[1], "B is pulled in and plays it too", starts=w.starts, log=w.log)
    w.until(lambda: len(w.ends[0]) >= len(w.starts[0]) and len(w.ends[1]) >= len(w.starts[1])
            and not any(w.on), 12000, lambda i: ("cross", "cross") if i % 60 < 2 else ("", ""))
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
    sys.path.insert(0, str(TOOLS["out"].parent.parent / "launcher"))
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
    w.until(lambda: boss(a), 4000, lambda i: (walk + ("+cross" if i % 90 < 12 else ""), ""))
    run.expect(boss(a), "A walks into the boss's room", at=a.snapshot())
    w.until(lambda: boss(g2), 900)
    run.expect(boss(g2), "B is pulled into the fight", b=g2.snapshot())
    hp_seen = {}
    fought = 0
    for t in range(limit):
        auth = a if a.mailbox("self_presence").role == ROLE_AUTHORITY else g2
        if t % 30 == 0:
            for slot, (eid, _, _, hp) in enemies(auth).items():
                hp_seen.setdefault(slot, hp)
                if hp > 8:
                    auth.write("g_Entities", 8, "<h", slot * 0xBC + 0x3E)
        w.step(1, (fight_pad(a, t=t), fight_pad(g2, t=t + 6)))
        fought = 0 if (boss(a) or boss(g2)) else fought + 1
        if fought > 300:
            break
    run.expect(fought > 300, "the boss falls: no fight in either game", hp_first=sorted(hp_seen.values())[-3:])
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
