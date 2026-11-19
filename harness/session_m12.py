"""M12 session tests (design/M12-coverage.md): cutscenes together, starting with the prologue
(playtest 2026-10-25 note 1: the Richter vs Dracula prologue didn't sync the players for its
scenes, nor for the scene after it)."""

import os
import struct

from coop_env import TOOLS
from session import session_scenario
from link.mailbox import BUSY, CUTSCENE  # noqa: E402 - session puts link on the path

ST0, NO3 = 0x1F, 0x41
FLAG_DEAD = 0x100  # include/game.h
PAD_SIM, DEMO_TIMER = 0x80072EF4, 0x80072EFC  # g_Player.padSim, g_Player.demo_timer


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


def stage(g):
    return g.read("g_StageId")


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


DEATH_ROOM = (20, 39)  # NO3: E_CUTSCENE runs the Death scene (savestates.py)
EQUIPMENT_OFS = 0x29C  # g_Status.equipment[0]


# --- the cutscene catalogue (design/M12 part 1) ----------------------------------------------
# name: (A's start: a fixture or a debug start, A's pad to walk into the scene, frames allowed).
# B starts at the castle entrance: it's pulled in, and both must play the scene together.
STARTS = TOOLS["out"].parent / "fixtures" / "debug-starts"
DECOMP = TOOLS["out"].parent / "src" / "sotn-decomp"
STAGE_IDS = {"nz0": 0x0C, "lib": 0x02, "dai": 0x06, "cen": 0x08, "top": 0x0B, "dre": 0x12}
# Scenes reached by sending A to the scene's room (its entity's layout in the decomp's
# assets/st/<stage>/entity_layouts.json), from the debug start nearest before it in the story.
# name: (base start, stage, entity layout, entity x, y, which side A comes from, the castle flag
# that marks the scene seen: include/castle_flags.h; it's cleared in both games first)
ROOM_SCENES = {
    "maria_alchemy_lab": ("Alchemy Laboratory", "nz0", 15, 128, 128, "left", 0x85),  # MET_MARIA_IN_NZ0
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


# --- the partner's attacks on screen (playtest 2026-10-25 note 2, sprites.c) ------------------
SUBWEAPON_ID, HEARTS_ADDR, DAGGER = 0x80097BFC, 0x80097BA8, 1


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


PICTURE = (60, 110, 240, 226)  # Now Loading's picture in the 256x240 frame, with a margin


def now_loading_clean(run, start):
    """Issue 268: a castle's save loads into a clean Now Loading screen, black around its picture:
    no title logo under it and no old tilemap drawing the new stage's tiles as garbage."""
    from link.mailbox import CMD_LOAD_SAVE, IN_PLAY
    from session import Session
    from module import COOP_DISC
    save = (STARTS / "Scene - The Librarian.save").read_bytes()
    out = TOOLS["out"] / run.name  # (game art: never in git)
    with Session(COOP_DISC, starts=(start, None)) as s:
        a = s.a
        state = 1 if start is None else 2  # Game_Title, Game_Play
        for _ in range(9000):
            s.step(1)
            if a.read("g_GameState") == state and (start or a.raw_frame()[0] == 512):
                break
        run.expect(a.read("g_GameState") == state, "the title" if start is None else "in play")
        s.step(30)
        a.mailbox("put_save", save)
        a.mailbox("command", CMD_LOAD_SAVE)
        out.mkdir(parents=True, exist_ok=True)
        worst, shots = 0.0, 0
        for i in range(3000):
            s.step(1)
            if a.read("g_GameState") == 4:  # Game_NowLoading
                img = a.screenshot()
                if img is not None and shots < 400:
                    w, h = img.size
                    px = img.convert("L").load()
                    # outside Now Loading's picture (its words and the logo: x 65-234, y 115-221)
                    border = [(x, y) for y in range(0, h, 2) for x in range(0, w, 2)
                              if not (PICTURE[0] <= x <= PICTURE[2] and PICTURE[1] <= y <= PICTURE[3])]
                    lit = sum(1 for x, y in border if px[x, y] > 24)
                    if lit / len(border) > worst:
                        worst = lit / len(border)
                        img.save(out / "worst_now_loading.png")
                    if shots % 30 == 0:
                        img.save(out / f"now_loading_{shots:03}.png")
                    shots += 1
            p = a.mailbox("self_presence")
            if p.flags & IN_PLAY and not p.flags & BUSY and shots:
                break
        run.expect(shots > 0, "Now Loading shows", frames=i)
        run.expect(worst < 0.002, "it is black around its picture", lit=round(worst, 4), shots=shots)
        run.expect(p.flags & IN_PLAY, "and play goes on in the save's castle", frames=i)


@session_scenario(starts=(None, None))
def solo_continue_now_loading_clean(run):
    """Continue from the title: no logo or old tiles around Now Loading."""
    now_loading_clean(run, None)


@session_scenario(starts=(str(STARTS / "Scene - The Librarian.state"), None))
def solo_continue_now_loading_clean_in_play(run):
    """A castle's save loading in play: the old room's tiles don't draw around Now Loading."""
    now_loading_clean(run, str(STARTS / "Scene - The Librarian.state"))


MET_MARIA_IN_CEN = 0xD8


# --- the partner's hand-weapon swings (note 2, phase 2: weapons.c) ---------------------------
def _swing_drawn(run, chars, button, item=None, settle=0):
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
    hand = 0  # the first hand: □ swings it, for everyone
    item = items[0] if item is None else item
    a.write(EQUIPMENT, item, "<I")
    as_characters(run, *chars)  # the load loads the weapon
    into_hall(run)
    got = False
    for _ in range(300):
        run.step(1)
        if b.read(WEAPON_PARTNER + hand * 0x8000, "<I") == WEAPON_MAGIC:
            got = True
            break
    run.expect(got, "B has A's weapon (its copy came through the link)", item=item,
               a_seq=a.mailbox("self_weapon_seq", hand))
    drawn_at = None
    drawn_sym = symbols()["g_CoopWeaponsDrawn"]
    for i in range(240):
        run.step(1, (button if i % 40 < 2 else "", ""))
        if b.read(drawn_sym, "<I"):
            drawn_at = i
            break
    run.expect(drawn_at is not None, "B draws A's swing", sprites=b.mailbox("partner_sprite_count"))
    run.step(settle)
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


@session_scenario(characters=(1, 0))
def partner_swing_drawn_richter(run):
    """Note 2, phase 2: Richter swings a sword in his first hand (D105, □) next to Alucard."""
    _swing_drawn(run, (1, 0), "square")


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




LIFE_UP_DROP = 23  # ITEMDROP_LIFE_VESSEL: a boss's Life Max Up (src/st/e_life_up.h), an E_PRIZE_DROP


def _life_ups(g):
    """[(slot, entity x, y in the room)] of the Life Max Ups lying in g's room."""
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    out = []
    for slot in range(64, 256):
        e = raw[slot * 0xBC:(slot + 1) * 0xBC]
        eid, params = struct.unpack_from("<H", e, 0x26)[0], struct.unpack_from("<H", e, 0x30)[0]
        if eid == 3 and params & 0x7FFF == LIFE_UP_DROP and struct.unpack_from("<H", e, 0x2C)[0] < 5:
            out.append((slot, struct.unpack_from("<h", e, 2)[0], struct.unpack_from("<h", e, 6)[0]))
    return out


@session_scenario(starts=(str(STARTS / "Boss - Slogra and Gaibon.state"),) * 2, characters=(0, 1))
def boss_life_up_once_alucard_and_richter(run):
    """#296 (1.1.1 playtest, Alchemy Lab: "item max up dup"): a boss leaves a Life Max Up when it
    falls. The two games each made one, each player took the one in their game, and each game sent
    its +5 to the partner: +10 each. Each player gets +5 from it, once."""
    from session_progress import status
    a, b = run.s.a, run.s.b
    before = {g.name: status(g)["hp_max"] for g in (a, b)}
    boss_flow(run, next(r for r in _bossstarts() if r["name"].startswith("Slogra")))
    seen = {g.name: 0 for g in (a, b)}
    for t in range(1800):
        for g in (a, b):
            ups = _life_ups(g)
            seen[g.name] = max(seen[g.name], len(ups))
            if ups and t % 20 == 0:  # the player steps onto it (the room's own coordinates)
                sx, sy = g.read("g_Tilemap", "<h", 0xA), g.read("g_Tilemap", "<h", 0xE)
                _, x, y = ups[0]
                g.write("g_Entities", x, "<h", 2)
                g.write("g_Entities", y, "<h", 6)
        run.step(1)
    gained = {g.name: status(g)["hp_max"] - before[g.name] for g in (a, b)}
    run.expect(any(seen.values()) or any(gained.values()), "the boss left a Life Max Up", seen=seen, gained=gained)
    run.expect(gained == {"A": 5, "B": 5}, "each player's max HP +5 from it, once", gained=gained, seen=seen)
