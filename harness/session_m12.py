"""M12 session tests (design/M12-coverage.md): cutscenes together, starting with the prologue
(playtest 2026-10-25 note 1: the Richter vs Dracula prologue didn't sync the players for its
scenes, nor for the scene after it)."""

import os

from coop_env import TOOLS
from session import session_scenario
from link.mailbox import BUSY, CUTSCENE  # noqa: E402 - session puts link on the path

ST0, NO3 = 0x1F, 0x41
FLAG_DEAD = 0x100  # include/game.h
PAD_SIM, DEMO_TIMER = 0x80072EF4, 0x80072EFC  # g_Player.padSim, g_Player.demo_timer
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
def prologue_opening(run):
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
def prologue_fight(run):
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
def death_waits_for_partner(run):
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
# Not yet triggered by the harness (GitHub issues), so not registered:
OPEN_SCENES = {
    # talking to him (Up next to his chair) didn't start it yet
    "librarian": ("Boss - Doppleganger10", "lib", 2, 80, 172, "right", 0x72),       # MET_LIBRARIAN
    # started once on arrival, then not when both games share the start: what else it needs is open
    "maria_chapel": ("Boss - Minotaur and Werewolf", "dai", 4, 256, 128, "left", 0x63),  # MET_MARIA_IN_DAI
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
    test.__name__ = f"scene_{name}"
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
    test.__name__ = f"scene_{name}"
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


GAME_TITLE, GAME_ENDING = 1, 9  # Game_Title, Game_Ending (include/game.h)
VISITED = 0x108  # g_Settings.D_8003CB00: a bit per time-attack event whose fight has started


def boss_flow(run, b, limit=24000):
    """A walks into the boss; B, at the door, is pulled in; the boss has twice its HP; both fight it
    (worn down: this tests the flow, not the fight); it falls once, both are fine after, and what
    the fight set in the castle flags is the same in both."""
    from link.mailbox import BOSS, BUSY, DEAD, IN_PLAY, ROLE_AUTHORITY
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
    if b.get("out"):  # started in the arena: out and back, so the boss spawns with co-op's HP
        import bossstarts
        from session_progress import arrive
        stage, room, x, y = b["out"]
        for g in (a, g2):
            arrive(run, g, bossstarts.STAGES[stage], room, x, y)
        run.step(60)
        from link.mailbox import CMD_ARRIVE
        stage, (room, x, y) = bossstarts.STAGES[b["stage"]], b["arrive"]
        for g in (a, g2):  # (his scene starts as they arrive: not back in play until it's done)
            g.mailbox("command", CMD_ARRIVE, stage, room, x, y)
        w.until(lambda: all((lambda q: q.stage == stage and q.room_id == room)(g.mailbox("self_presence"))
                            for g in (a, g2)), 900)
    # B walks too, as a player would (some arenas open with a scene that only moves on while the
    # player holds a direction); it stays where it is otherwise (the door's edge)
    w.until(lambda: boss(a), 4000, lambda i: (walk + ("+cross" if i % 90 < 12 else ""),
                                              walk if g2.read("g_CutsceneHasControl") else ""))
    run.expect(boss(a), "A walks into the boss's room", at=a.snapshot())
    # a pulled-in partner may first play the arena's scene (Minotaur & Werewolf), which steers it
    # only while a direction is held (like the prologue's)
    w.until(lambda: boss(g2), 3000, ("", walk))
    run.expect(boss(g2), "B is pulled into the fight", b=g2.snapshot())
    # Into the arena (the inverted castle's): some fights start (and later record the win) only
    # once the player is well inside (Akmodan II's manager: x 128-384; the trio's: 224-320), and
    # the fight bot stops near the boss. The fight's start sets its time-attack event's visited bit
    # (TimeAttackController). Not in the first castle: held there, the walk took A through the
    # Succubus's scene and the chain lost her fight (and it gave no missing record back).
    import bossstarts
    event = bossstarts.EVENTS.get(b.get("event")) if b.get("inverted") else None
    if event is not None:
        visited = lambda: a.read("g_Settings", "<I", VISITED) & (1 << event)
        w.until(visited, 600, (walk, ""))  # (not every fight sets it: Death's doesn't)
    hp_seen = {}
    fought = 0
    role_log = []
    free = 0  # frames of the fight outside scenes (Dracula talks for some 2,900 first)
    split, splits = 0, []
    for t in range(limit):
        pa, pb = a.mailbox("self_presence"), g2.mailbox("self_presence")
        if not role_log or role_log[-1][1:] != (pa.role, pb.role, pa.flags, pb.flags):
            role_log = (role_log + [(t, pa.role, pb.role, pa.flags, pb.flags)])[-14:]
        auth = a if pa.role == ROLE_AUTHORITY else g2
        free += not auth.read("g_CutsceneHasControl")
        # D131: while both are in the boss's room, the fight stays shared (one boss, two players)
        same_room = (pa.stage, pa.room_id) == (pb.stage, pb.room_id) and pa.flags & pb.flags & IN_PLAY
        if same_room and bool(pa.flags & BOSS) != bool(pb.flags & BOSS) and not (pa.flags | pb.flags) & BUSY:
            split += 1
            if split == 120 and not splits:
                splits.append({"t": t, "a": a.snapshot(), "b": g2.snapshot(), "roles": (pa.role, pb.role),
                               "flags": (pa.flags, pb.flags), "role_log": list(role_log)})
        else:
            split = 0
        if t % 30 == 0:
            for g in (a, g2):  # the players don't die: this tests the flow, not the bot's fighting
                g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            # the room's authority runs its enemies; a room that isn't shared (a split, a player
            # knocked out of the arena), each game its own (else A's boss was never worn down)
            for g in ((auth,) if pa.role or pb.role else (a, g2)):
                for slot, (eid, _, _, hp) in enemies(g).items():
                    hp_seen.setdefault(slot, hp)
                    if hp > 8:
                        g.write("g_Entities", 8, "<h", slot * 0xBC + 0x3E)
                    elif free > FIGHT_FREE:  # the bot can't land the last hit (flying bosses): a scripted
                        # kill, as the game's hit detection does when HP runs out (design/M12 part 2)
                        g.write("g_Entities", 0, "<h", slot * 0xBC + 0x3E)
                        flags = g.read("g_Entities", "<I", slot * 0xBC + 0x34)
                        g.write("g_Entities", flags | FLAG_DEAD, "<I", slot * 0xBC + 0x34)
        w.step(1, (fight_pad(a, t=t), fight_pad(g2, t=t + 6)))
        fought = 0 if (boss(a) or boss(g2)) else fought + 1
        if fought > 300:
            break
    run.expect(not splits, "the fight stays shared while both are in its room (D131)", split=splits[:1])
    run.expect(fought > 300, "the boss falls: no fight in either game", hp_first=sorted(hp_seen.values())[-3:],
               boss=[bool(boss(g)) for g in (a, g2)], roles=[g.mailbox("self_presence").role for g in (a, g2)],
               left=[sorted((v[0], v[3]) for v in enemies(g).values())[:6] for g in (a, g2)],
               cs=[g.read("g_CutsceneHasControl") for g in (a, g2)], role_log=role_log)
    if b["name"] not in ("Richter", "Dracula"):
        w.step(300)
    else:
        # Killing him (not freeing him: the Holy Glasses, Shaft's orb) ends the game: his death
        # scene fades to white and the ending plays (BO6's e_cutscene_actors). No castle flag
        # records it: the game he died in tells the partner's (EV_KILLED, boss.c), whose own Richter
        # dies too and whose scene plays with it; a partner that can't (dead, elsewhere) follows it
        # into the ending. Either way, the two endings start together. The fade takes some 320 frames.
        ended, back = [None, None], []

        def both_ended():
            for k, g in enumerate((a, g2)):
                if ended[k] is None and g.read("g_GameState") in (GAME_ENDING, GAME_TITLE):  # its ending, then the title
                    ended[k] = w.t
                if ended[k] is None:  # still kept alive: what's left of his attacks lands in the fade
                    g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
                    if boss(g):
                        back.append("AB"[k])
            if os.environ.get("BOSS_DEBUG") and w.t % 300 == 0:
                print(w.t, [(g.read("g_GameState"), g.read("g_CutsceneHasControl"), g.mailbox("self_presence").flags,
                             g.snapshot()["world_x"], g.snapshot()["stage"]) for g in (a, g2)], flush=True)
            return None not in ended
        w.until(both_ended, 2400 if b["name"] == "Richter" else 6000)  # Dracula's last words: some 4,400 frames
        run.expect(None not in ended, f"killing {b['name']} ends the game, in both games (as alone)",
                   ended=ended, states=[g.read("g_GameState") for g in (a, g2)])
        run.expect(not back, "he doesn't come back in either game", back=sorted(set(back)))
        run.expect(None not in ended and abs(ended[0] - ended[1]) <= 30, "both endings start together",
                   ended=ended)
        return
    for g, n in ((a, "A"), (g2, "B")):
        p = g.mailbox("self_presence")
        run.expect(p.flags & IN_PLAY and not p.flags & DEAD, f"{n} is in play and alive after", flags=p.flags,
                   state=(g.read("g_GameState"), g.read("g_GameStep"), g.read("g_GameEngineStep"), g.read("g_CutsceneHasControl")), where=g.snapshot())
    flags = [g.read_bytes("g_CastleFlags", 0x300) for g in (a, g2)]
    diff = [i for i in range(0x300) if (flags[0][i] != flags0[0][i] or flags[1][i] != flags0[1][i])
            and flags[0][i] != flags[1][i]]
    run.expect(not diff, "what the fight set in the castle flags is the same in both", diff=diff[:10])
    if b.get("event"):  # the inverted castle's: its own death sequence records it (in both games: EV_RECORD)
        k = bossstarts.RECORDS + 4 * bossstarts.EVENTS[b["event"]]
        w.until(lambda: all(g.read("g_Settings", "<i", k) for g in (a, g2)), 1800)
        rec = [g.read("g_Settings", "<i", k) for g in (a, g2)]
        run.expect(all(rec), "the boss is beaten in both games, by the game's own record", records=rec,
                   hp_first=sorted(hp_seen.values())[-3:], t=t)


FIGHT_FREE = 3000  # frames of a fight outside scenes before the scripted kill


def boss_alone(run, g, name, limit=12000):
    """g walks into the boss (its start's row in bossstarts) and fights it alone, kept alive and
    the boss worn down, the last hit scripted if the bot can't land it (as in boss_flow). Returns
    when no boss has been in g's room for 300 frames."""
    from link.mailbox import BOSS
    import bossstarts
    b = next(r for r in bossstarts.B if r["name"] == name)
    pad = (lambda p: (p, "")) if g is run.s.a else (lambda p: ("", p))
    boss = lambda: g.mailbox("self_presence").flags & BOSS
    for _ in range(4000):
        if boss():
            break
        run.step(1, p1=pad(b["walk"]))
    run.expect(boss(), f"{name} is there")
    event = bossstarts.EVENTS.get(b.get("event")) if b.get("inverted") else None
    for _ in range(600 if event is not None else 0):
        if g.read("g_Settings", "<I", VISITED) & (1 << event):
            break
        run.step(1, p1=pad(b["walk"]))
    free = gone = 0
    for t in range(limit):
        free += not g.read("g_CutsceneHasControl")
        if t % 30 == 0:
            g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            for slot, (_, _, _, hp) in enemies(g).items():
                if hp > 8:
                    g.write("g_Entities", 8, "<h", slot * 0xBC + 0x3E)
                elif free > FIGHT_FREE:
                    g.write("g_Entities", 0, "<h", slot * 0xBC + 0x3E)
                    flags = g.read("g_Entities", "<I", slot * 0xBC + 0x34)
                    g.write("g_Entities", flags | FLAG_DEAD, "<I", slot * 0xBC + 0x34)
        run.step(1, p1=pad(fight_pad(g, t=t)))
        gone = 0 if boss() else gone + 1
        if gone > 300:
            return
    run.expect(False, f"{name} falls", left=sorted(enemies(g).values())[:4])


def _boss_test(b):
    name = b["name"].replace(" & ", " and ")
    def test(run):
        boss_flow(run, b)
    test.__name__ = "boss_" + name.lower().replace(",", "").replace(" ", "_")
    test.__doc__ = f"Every boss, together: {b['name']} ({b['area']})."
    start = str(STARTS / f"Boss - {name}.state")
    session_scenario(starts=(start, start))(test)


for _b in _bossstarts():
    _boss_test(_b)


# --- the partner's attacks on screen (playtest 2026-10-25 note 2, sprites.c) ------------------
SUBWEAPON_ID, HEARTS_ADDR, DAGGER = 0x80097BFC, 0x80097BA8, 1


def attack_pixels(run, chars, pad, every=30, arm=None, setup=None, samples=(4, 8, 12, 16)):
    """M13 (criterion 2): what A adds to B's screen (partner_pixels: B drawn with and without its
    partner), standing, then mid-attack; A's body in B's game draws its own attacks, so the attack
    adds to it. arm(a): set A up for the attack (a subweapon) before each press. pad: the press
    (held 2 frames of each `every`), or a function (try, frame) giving A's pad (a sequence)."""
    from link.mailbox import BUSY, IN_PLAY
    from session_m8 import as_characters
    from session_scenarios import partner_pixels
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    if setup:  # before the load (it loads A's weapon)
        setup(a)
    if chars != (0, 0) or setup:
        as_characters(run, *chars)
    into_hall(run)
    for _ in range(900):  # B in play in A's room (its arrival can still be loading)
        run.step(1)
        pa, pb = a.mailbox("self_presence"), b.mailbox("self_presence")
        if pa.room == pb.room and pb.flags & IN_PLAY and not pb.flags & BUSY:
            break
    run.step(30)
    box, idle, _ = partner_pixels(b)
    best, wide = 0, 0
    width = (box[2] - box[0]) if box else 0
    for i in range(4 * every):
        if arm:
            arm(a)
        now = pad(i // every, i % every) if callable(pad) else pad if i % every < 2 else ""
        run.step(1, (now, ""))
        if i % every in samples:  # the attack's frames
            bb, n, _ = partner_pixels(b)
            best = max(best, n)
            wide = max(wide, (bb[2] - bb[0]) - width if bb else 0)
    # A weapon, a whip, a dagger reach out of the body: wider, or more pixels than standing
    return idle, best if wide < 8 else max(best, idle + 21)


@session_scenario(characters=(1, 1))  # CHAR_RICHTER twice
def partner_attack_drawn(run):
    """Note 2 (since M13: the partner's body draws it): A (Richter) whips next to B (Richter), and
    B's screen shows it: A adds more to B's picture mid-whip than standing."""
    idle, whip = attack_pixels(run, (1, 1), "square")
    run.expect(idle > 100, "B draws A", pixels=idle)
    run.expect(whip > idle + 50, "and A's whip", standing=idle, whipping=whip)


@session_scenario()
def partner_dagger_drawn(run):
    """Note 2, phase 1b (since M13: the partner's body throws it): A (Alucard) throws daggers next
    to B, and B's screen shows them."""
    def arm(a):
        a.write(SUBWEAPON_ID, DAGGER, "<i")
        a.write(HEARTS_ADDR, 99, "<i")
    idle, thrown = attack_pixels(run, (0, 0), "up+square", arm=arm)
    run.expect(idle > 100, "B draws A", pixels=idle)
    run.expect(thrown > idle + 20, "and A's daggers", standing=idle, throwing=thrown)


# --- every boss with other characters (design/M12 part 2: R+M and A+R) ------------------------
PAIRINGS = {"rm": (1, 2), "ar": (0, 1)}  # CHAR_* of A and B
CHAR_NAMES = ("alucard", "richter", "maria")


def _boss_pair_test(b, tag, chars):
    name = b["name"].replace(" & ", " and ")

    def test(run):
        import sys
        from pathlib import Path
        from session_m8 import as_characters
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
        import bossstarts
        from link.mailbox import CMD_ARRIVE
        from session_progress import arrive
        if b.get("out"):  # a start in the arena (Dracula's): the save and its load out of it
            for g in (run.s.a, run.s.b):
                arrive(run, g, bossstarts.STAGES[b["out"][0]], *b["out"][1:])
        as_characters(run, *chars)
        # the load puts them back at the save's room, not at the boss's door: back to the start's spot
        stage = bossstarts.STAGES[b["stage"]]
        room, x, y = b["arrive"]
        for g in (run.s.a, run.s.b):
            g.mailbox("command", CMD_ARRIVE, stage, room, x, y)
        run.step(240)
        boss_flow(run, b)
    test.__name__ = "boss_" + name.lower().replace(",", "").replace(" ", "_") + "_{}_and_{}".format(*(CHAR_NAMES[c] for c in chars))
    test.__doc__ = f"{b['name']} together, as {tag.upper()} (Alucard, Richter, Maria)."
    start = str(STARTS / f"Boss - {name}.state")
    session_scenario(starts=(start, start), characters=chars, full=True)(test)  # the pairings: --full


for _b in _bossstarts():
    if _b["name"] == "Succubus":  # the Nightmare: no saving there, so no character change at her door
        continue
    for _tag, _chars in PAIRINGS.items():
        _boss_pair_test(_b, _tag, _chars)


def _start_scene_test(name, start, walk):
    def test(run):
        scene_together(run, walk, 3000)
    test.__name__ = f"scene_{name}"
    test.__doc__ = f"Cutscene catalogue, from its scene start: {start}."
    path = str(STARTS / f"{start}.state")
    session_scenario(starts=(path, path))(test)


for _name, (_start, _walk) in START_SCENES.items():
    _start_scene_test(_name, _start, _walk)


LIBRARIAN_STARTS = (str(STARTS / "Scene - The Librarian.state"), str(STARTS / "Boss - Lesser Demon.state"))
SHOP_ENTITY = 0x801B15C0  # his shop menu's entity (lib e_shop.c, func_us_801B15C0)


def in_shop(g):
    return any(g.read(0x800733D8 + k * 0xBC + 0x28) == SHOP_ENTITY for k in range(64, 256))


def librarian_shop(run, chars):
    """A walks in to the Librarian and leaves through his menu's Exit; B is never involved, and
    never held (his scene keeps control for all of A's visit: issue 19's softlock)."""
    as_at_start(run, *chars)
    a, b = run.s.a, run.s.b
    for g in (a, b):  # B, elsewhere with the same progress, hasn't met him either
        g.write("g_CastleFlags", 0, "<B", 0x72)
    room = b.snapshot()["room"]
    w = SceneWatch(run)
    w.until(lambda: w.starts[0], 3000, lambda i: ("left+cross" if i % 40 < 10 else "left", ""))
    run.expect(w.starts[0], "A's scene starts", at=a.snapshot())
    w.until(lambda: in_shop(a), 6000)
    run.expect(in_shop(a), "A ends at his shop", log=w.log)
    run.expect(not w.starts[1] and b.snapshot()["room"] == room, "B isn't pulled in", starts=w.starts, at=b.snapshot())
    run.expect(not b.mailbox("partner_presence").flags & (CUTSCENE | BUSY), "and doesn't see a scene or a busy partner")
    x = b.snapshot()["world_x"]
    w.step(60, ("", "right"))
    run.expect(b.snapshot()["world_x"] != x, "B keeps playing", at=b.snapshot())
    w.until(lambda: a.read(DEMO_TIMER, "<i") == 0 and a.snapshot()["x"] < 0x80, 600)  # in the chair
    w.step(120)
    w.step(2, ("triangle", ""))  # his menu's Exit; the script walks on, then gives the pad back
    w.step(120)
    tries = w.until(lambda: not a.read("g_CutsceneHasControl"), 900, lambda i: ("right+cross" if i % 40 < 10 else "right", ""))
    run.expect(not a.read("g_CutsceneHasControl"), "A walks out through the menu's Exit", tries=tries, at=a.snapshot())
    w.step(120)
    x = a.snapshot()["world_x"]
    w.step(60, ("right", ""))
    run.expect(a.snapshot()["world_x"] != x, "A plays on", at=a.snapshot())


@session_scenario(starts=LIBRARIAN_STARTS)
def librarian_shop_alucard(run):
    """The shop, Alucard in it."""
    librarian_shop(run, (0, 0))


@session_scenario(starts=LIBRARIAN_STARTS, characters=(1, 0))
def librarian_shop_richter(run):
    """The shop, Richter in it: the pairing that softlocked (issue 19)."""
    librarian_shop(run, (1, 0))


KEEP_START = str(STARTS / "Scene - The Castle Keep.state")


def as_at_start(run, ca, cb):
    """A debug start holds Alucard: the characters, then back to the start's spot (see
    _boss_pair_test: a character change is a load, which goes to the save's room)."""
    from link.mailbox import CHAR_ALUCARD, CMD_ARRIVE
    from session_m8 import as_characters
    games = (run.s.a, run.s.b)
    spots = [g.mailbox("self_presence") for g in games]
    as_characters(run, ca, cb)
    for g, p in zip(games, spots):
        g.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)
    run.step(240)
    played = [g.mailbox("self_presence").character for g in games]
    run.expect(played == [ca, cb], "the characters are in play", played=played, alucard=CHAR_ALUCARD)


def keep_scene(run, ca, cb):
    """Issue 20: the scene after Richter's fight (top post_richter_cutscene.c). It steers each
    player left, holds Cross for a jump only Alucard makes, and only ends at the warp."""
    as_at_start(run, ca, cb)
    a, b = run.s.a, run.s.b
    w = SceneWatch(run)
    w.until(lambda: w.starts[0] or w.starts[1], 900, ("right", "right"))
    run.expect(w.starts[0] or w.starts[1], "the scene starts", at=a.snapshot())
    seen, done, free = [], [False, False], [0, 0]
    for t in range(9000):
        w.step(1)
        if t % 300 == 0:
            seen.append([(g.snapshot()["world_x"], g.snapshot()["world_y"]) for g in (a, b)])
        # With the Holy Glasses worn the script lets go at the first landing (step 5): free to walk.
        free = [0 if t < 2700 or g.read(DEMO_TIMER, "<i") else free[k] + 1 for k, g in enumerate((a, b))]
        done = [g.read("g_StageId") != 0x0B or g.snapshot()["world_x"] < 0x200 or free[k] > 120 for k, g in enumerate((a, b))]
        if all(done):
            break
    run.expect(all(done), "both players get over the ledge, or are let go", frames=t, seen=seen, a=a.snapshot(), b=b.snapshot())
    for g, k in zip((a, b), free):
        if k > 120:
            x = g.snapshot()["world_x"]
            w.step(60, ("right", "right"))
            run.expect(g.snapshot()["world_x"] != x, "a player let go can walk", at=g.snapshot())


@session_scenario(starts=(KEEP_START, KEEP_START), characters=(0, 1))
def keep_scene_alucard_and_richter(run):
    """The Keep's scene, the pairing that softlocked."""
    keep_scene(run, 0, 1)


@session_scenario(starts=(KEEP_START, KEEP_START), characters=(1, 2))
def keep_scene_richter_and_maria(run):
    """The Keep's scene, with no Alucard."""
    keep_scene(run, 1, 2)


@session_scenario()
def report_state_still_loads(run):
    """F9 scrubs savestates: one with its folders and a name overwritten still loads (replay.py)."""
    import sys
    from pathlib import Path
    from module import COOP_DISC
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
    import report
    a = run.s.a
    folder = str(Path(COOP_DISC).resolve().parent)
    state = a.save_state()
    run.expect(folder.encode() in state, "a savestate holds the disc's folder")
    clean = report.scrub_bytes(state, [folder, str(Path.home()), "Richter"])
    run.expect(folder.encode() not in clean and len(clean) == len(state), "the scrub takes it out, at the same size")
    a.load_state(clean)
    frame = a.mailbox("self_presence").frame
    run.step(60)
    run.expect(a.mailbox("self_presence").frame != frame, "and the game runs on from it")


@session_scenario(starts=(None, None))
def solo_continue_picture_width(run):
    """Issue 24: Continue from the title, one game: the picture is the game's 256 wide, not the
    title's 512 with the game in its left half."""
    from link.mailbox import CMD_LOAD_SAVE, IN_PLAY
    from session import Session
    from module import COOP_DISC
    save = (STARTS / "Scene - The Librarian.save").read_bytes()
    with Session(COOP_DISC, starts=(None, None)) as s:
        a = s.a
        for _ in range(9000):
            s.step(1)
            if a.read("g_GameState") == 1 and a.raw_frame()[0] == 512:
                break
        run.expect(a.raw_frame()[0] == 512, "the title is 512 wide", width=a.raw_frame()[0])
        a.mailbox("put_save", save)
        a.mailbox("command", CMD_LOAD_SAVE)
        for i in range(3000):
            s.step(1)
            p = a.mailbox("self_presence")
            if p.flags & IN_PLAY and not p.flags & BUSY:
                break
        run.expect(p.flags & IN_PLAY, "in play", frames=i)
        s.step(120)
        run.expect(a.raw_frame()[0] == 256, "the picture is the game's width", width=a.raw_frame()[0])


CENTER_START = str(STARTS / "Scene - Maria in the Center - the Holy Glasses.state")
MET_MARIA_IN_CEN = 0xD8


def maria_center(run, ca, cb):
    """Issue 62: both players ride the lift to Maria, and her scene ends with her flag set."""
    as_at_start(run, ca, cb)
    a, b = run.s.a, run.s.b
    w = SceneWatch(run)
    pad = lambda g: "left" if g.snapshot()["world_x"] > 392 and not g.read(DEMO_TIMER, "<i") else ""
    w.until(lambda: all(g.read("g_CastleFlags", "<B", MET_MARIA_IN_CEN) for g in (a, b)), 6000,
            lambda i: (pad(a), pad(b)))
    flags = [g.read("g_CastleFlags", "<B", MET_MARIA_IN_CEN) for g in (a, b)]
    run.expect(flags == [1, 1], "her scene ends in both games", flags=flags, log=w.log, a=a.snapshot(), b=b.snapshot())
    w.step(180)
    control = control_back(run, w)
    run.expect(all(f is not None for f in control), "both players get control back", control=control)


@session_scenario(starts=(CENTER_START, CENTER_START))
def scene_maria_center_from_start(run):
    """Maria in the Center, as Alucard twice."""
    maria_center(run, 0, 0)


@session_scenario(starts=(CENTER_START, CENTER_START), characters=(1, 2))
def scene_maria_center_richter_and_maria(run):
    """Maria in the Center, with no Alucard."""
    maria_center(run, 1, 2)


def keep_a_long_fight(run):
    """Issue 60: nobody hits Karasuman, so his fight lasts, and it stays one fight in one room."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
    import bossstarts
    from link.mailbox import BOSS, ROLE_AUTHORITY, ROLE_GUEST
    row = next(r for r in bossstarts.B if r["name"] == "Karasuman")
    a, b = run.s.a, run.s.b
    w = SceneWatch(run)
    boss = lambda g: g.mailbox("self_presence").flags & BOSS
    w.until(lambda: boss(a), 2000, lambda i: (row["walk"] + ("+cross" if i % 90 < 12 else ""), ""))
    run.expect(boss(a), "A walks into his fight", at=a.snapshot())
    w.until(lambda: boss(b), 1200, ("", row["walk"]))
    run.expect(boss(b), "B is pulled in", at=b.snapshot())
    w.step(60)
    apart, longest, run_apart = [], 0, 0
    for t in range(1800):
        w.step(1)
        if t % 30 == 0:
            for g in (a, b):  # no one dies: the fight is what's being watched
                g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
        pa, pb = a.mailbox("self_presence"), b.mailbox("self_presence")
        if not (pa.room_id == pb.room_id and pa.flags & pb.flags & BOSS and
                {pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}):
            apart.append((t, pa.room_id, pb.room_id, pa.flags, pb.flags, pa.role, pb.role))
            run_apart += 1
            longest = max(longest, run_apart)
        else:
            run_apart = 0
    # He can knock a player out of the door: the pull-in brings them back (BOSS_PULL_COOLDOWN: 10 s).
    run.expect(longest < 780, "a player knocked out is brought back", longest=longest, apart=apart[:6])
    run.expect(not run_apart, "the fight ends up as one room, one boss, one authority", at=(a.snapshot(), b.snapshot()), apart=apart[-3:])


@session_scenario(starts=(str(STARTS / "Boss - Karasuman.state"),) * 2)
def boss_karasuman_stays_shared(run):
    """Issue 60, from his boss start."""
    keep_a_long_fight(run)


# --- doors in a shared room (D107) ----------------------------------------------------------
@session_scenario(starts=("no1", "no1"))
def guest_opens_red_door(run):
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
def partner_swing_drawn(run):
    """Note 2, phase 2: Alucard swings a sword next to Alucard."""
    _swing_drawn(run, (0, 0), "square")


@session_scenario(characters=(1, 0))
def partner_swing_drawn_richter(run):
    """Note 2, phase 2: Richter swings his off-hand sword (D105) next to Alucard."""
    _swing_drawn(run, (1, 0), "circle")


# --- the first castle, chained (design/M12-v1-release.md criterion 8; D120) -------------------
@session_scenario(starts=(str(STARTS / "Boss - Slogra and Gaibon.state"),) * 2, full=True)
def boss_chain_first_castle_long(run):
    """Both games play the first castle's 12 bosses in route order, carrying what they earn (level,
    experience, gold, items, castle flags) from each fight to the next. Between bosses they travel
    by teleport, picking up that stretch's relics and story flags (the walks themselves are covered
    by the gate and movement tests, D119). At the end every boss is beaten in both games, by the
    game's own records, and the two castles match."""
    chain(run, lambda r: not r.get("inverted"))


@session_scenario(starts=(str(STARTS / "Boss - The Creature.state"),) * 2, full=True)
def boss_chain_inverted_castle_long(run):
    """The inverted castle's bosses, chained as the first castle's (boss_chain_first_castle_long),
    from the Creature to Galamoth (Dracula ends the game: boss_dracula). Each fight must leave
    its record in both games (boss_flow)."""
    chain(run, lambda r: r.get("inverted") and r["name"] != "Dracula")


def chain(run, which):
    """The chained playthrough of the boss rows `which` picks (bossstarts.B), in order."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
    import bossstarts
    from link.mailbox import CMD_ARRIVE
    a, b = run.s.a, run.s.b
    level0 = [g.read("g_Status", "<i", 0x80097BE8 - 0x80097964) for g in (a, b)]
    beaten, missing = [], set()
    for boss in [r for r in bossstarts.B if which(r)]:
        for g in (a, b):  # this stretch's pickups and story; what was earned is kept as it is
            for name in boss["relics"]:
                k = bossstarts.RELICS.index(name)
                if not g.read("g_Status", "<B", k):
                    g.write("g_Status", 1 if name in bossstarts.CARDS else 3, "<B", k)
            for name in boss["flags"]:
                for f in bossstarts.FLAGS[name]:
                    g.write("g_CastleFlags", 1, "<B", f)
            warps = sum(bit for area, bit in bossstarts.WARPS.items() if area in boss["areas"])
            g.write("g_CastleFlags", g.read("g_CastleFlags", "<B", bossstarts.WRP_UNLOCKS) | warps, "<B",
                    bossstarts.WRP_UNLOCKS)
        room, x, y = boss["arrive"]
        for g in (a, b):
            g.mailbox("command", CMD_ARRIVE, bossstarts.STAGES[boss["stage"]], room, x, y)
        run.step(240)
        if os.environ.get("BOSS_DEBUG"):
            print("CHAIN", boss["name"], [g.snapshot() for g in (a, b)], flush=True)
        if os.environ.get("CHAIN_SAVE_AT") == boss["name"]:  # both games here, to start a test from
            for g, n in ((a, "a"), (b, "b")):
                g.save_state_file(str(TOOLS["out"] / f"chain_at_{n}.state"))
        boss_flow(run, boss)
        beaten.append(boss["name"])
        records = lambda: [[g.read("g_Settings", "<i", bossstarts.RECORDS + 4 * bossstarts.EVENTS[n.lower()])
                            for n in beaten if n.lower() in bossstarts.EVENTS] for g in (a, b)]
        for _ in range(1800):  # a boss's own death sequence sets its record (the Lesser Demon's is long)
            if all(all(r) for r in records()):
                break
            if _ % 30 == 0:  # kept alive, as in the fight: a scripted kill can leave a boss's parts
                for g in (a, b):  # behind (Olrox's), still hurting
                    g.write("g_Status", g.read("g_Status", "<i", 0x240), "<i", 0x23C)
            run.step(1)
        # Reported, not asserted: a boss the bot can't finish gets a scripted kill (boss_flow), which
        # can skip the death sequence that writes the record (the Lesser Demon: STATUS, playtest list).
        run.log(f"after {boss['name']}: records {records()}") if hasattr(run, "log") else None
        missing.update(n for n, r in zip([n for n in beaten if n.lower() in bossstarts.EVENTS], records()[0]) if not r)
    level = [g.read("g_Status", "<i", 0x80097BE8 - 0x80097964) for g in (a, b)]
    run.expect(level[0] > level0[0] and level == [level[0]] * 2, "both levelled up, to the same level (M11)",
               start=level0, end=level)
    flags = [g.read_bytes("g_CastleFlags", 0x300) for g in (a, b)]
    run.expect(flags[0] == flags[1], "the two castles match at the end",
               diff=[i for i in range(0x300) if flags[0][i] != flags[1][i]][:10])
    (TOOLS["out"] / run.name).mkdir(parents=True, exist_ok=True)
    (TOOLS["out"] / run.name / "records.txt").write_text(f"bosses without a time-attack record: {sorted(missing)}\n")
