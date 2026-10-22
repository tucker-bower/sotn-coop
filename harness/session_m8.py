"""M8 session tests (design/M8-maria-and-richter.md): mixed teams in two linked games."""

from session import session_scenario  # first: puts `link` on the path

from bots import walker
import hashlib

from link.mailbox import (BUSY, CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW,
                          IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST)
from module import COOP_DISC
from session_progress import arrive
from session_scenarios import partner_pixels
from session_shared import into_hall, roles, stage_entities
import savestates as route

NAMES = {CHAR_ALUCARD: "Alucard", CHAR_RICHTER: "Richter", CHAR_MARIA: "Maria"}
STATUS = 0x80097964  # g_Status (include/game.h)
HEARTS, SUBWEAPON = 0x80097BA8, 0x80097BFC
VCOUNT = 0x801362D4  # D_801362D4 (DRA): GsGetVcount() after the frame's drawing
STAGE_NO3, HALL_ROOM_ID = 0x41, 72  # the castle entrance, and its zombie hall (room 14,40)


def reload_game(run, g, limit=3000):
    """A joint save and its load in game g: how Continue brings in each player's character."""
    seq, p = g.mailbox("save_seq"), g.mailbox("self_presence")
    g.mailbox("command", CMD_SAVE_NOW, p.stage, 0, p.room_left, p.room_top)
    for _ in range(limit):
        run.step(1)
        if g.mailbox("save_seq") != seq:
            break
    g.mailbox("put_save", g.mailbox("save_out"))
    g.mailbox("command", CMD_LOAD_SAVE)
    for _ in range(600):
        run.step(1)
        if g.read("g_GameState") == route.GAME_NOW_LOADING:
            break
    for _ in range(limit):
        run.step(1)
        q = g.mailbox("self_presence")
        if g.read("g_GameState") == route.GAME_PLAY and q.flags & IN_PLAY and not q.flags & BUSY:
            return True
    return False


def mixed_pair(run, ca, cb):
    """M8 criterion 3 (first part): A and B, as these characters, share the entrance hall. B is
    the guest, sees A's enemies, and B's hits count in A's world. Each draws the other's animated
    puppet (and the clip shows it)."""
    a, b = run.s.a, run.s.b
    for g, c in ((a, ca), (b, cb)):
        if c != CHAR_ALUCARD:
            run.expect(reload_game(run, g), f"{'AB'[g is b]} loads as {NAMES[c]}")
    run.expect((a.mailbox("self_presence").character, b.mailbox("self_presence").character) == (ca, cb),
               f"A plays {NAMES[ca]}, B {NAMES[cb]}")
    if ca == CHAR_ALUCARD:
        into_hall(run)
    else:  # a load starts at the room's default spot, below the way to the hall: go there
        arrive(run, a, STAGE_NO3, HALL_ROOM_ID, 1300, 200)
        run.step(120)
        arrive(run, b, STAGE_NO3, HALL_ROOM_ID, 1324, 200)
        run.step(30)
    run.expect(roles(run) == (ROLE_AUTHORITY, ROLE_GUEST), "they share the room: A authority, B guest",
               roles=roles(run))
    for viewer, other in ((a, cb), (b, ca)):
        _, count, _ = partner_pixels(viewer)
        run.expect(count > 150, f"{'AB'[viewer is b]} draws {NAMES[other]}'s puppet", pixels=count)
    ea, eb = stage_entities(a), stage_entities(b)
    run.expect(set(eb) == set(ea), "B's world has exactly A's stage entities")
    # B walks into the room (away from the nearer wall), attacking. Any enemy losing HP in A's
    # world counts: A stands still, so only B's hits can do it (zombies spawn as B goes).
    bot = walker("right" if b.snapshot()["x"] < 128 else "left", attack_every=30)
    prev, hit = stage_entities(a), []
    for i in range(1500):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        now = stage_entities(a)
        hit = [s for s, e in now.items() if s in prev and prev[s][0] == e[0] and e[3] < prev[s][3] < 32767]
        if hit:
            break
        prev = now
    run.expect(hit, f"{NAMES[cb]}'s hits hurt A's enemies (in A's world)")


@session_scenario(characters=(CHAR_ALUCARD, CHAR_RICHTER))
def mixed_party_shared_room(run):
    """Alucard (A) and Richter (B): mixed_pair."""
    mixed_pair(run, CHAR_ALUCARD, CHAR_RICHTER)


@session_scenario(characters=(CHAR_ALUCARD, CHAR_MARIA))
def mixed_party_shared_room_am(run):
    """Alucard (A) and Maria (B): mixed_pair."""
    mixed_pair(run, CHAR_ALUCARD, CHAR_MARIA)


@session_scenario(characters=(CHAR_RICHTER, CHAR_MARIA))
def mixed_party_shared_room_rm(run):
    """Richter (A) and Maria (B): mixed_pair."""
    mixed_pair(run, CHAR_RICHTER, CHAR_MARIA)


@session_scenario(characters=(CHAR_MARIA, CHAR_MARIA))
def char_select_session(run):
    """M8 criterion 2: all 9 pairs, one after another from the same playthrough (each a joint
    save and its load with new picks: how Continue with different characters works). Each game
    plays its pick: it walks, jumps and throws a subweapon for hearts. The disc never changes."""
    disc = COOP_DISC.with_suffix(".bin")
    before = hashlib.sha1(disc.read_bytes()).hexdigest()
    games = (run.s.a, run.s.b)
    for ca in NAMES:
        for cb in NAMES:
            for g, c in zip(games, (ca, cb)):
                g.host("set_player", character=c)
            pair = f"{NAMES[ca]} + {NAMES[cb]}"
            loaded = [reload_game(run, g) for g in games]
            run.expect(all(loaded), f"{pair}: both load", loaded=loaded,
                       states=[(g.read("g_GameState"), g.read("g_GameStep"), hex(g.mailbox("self_presence").flags),
                                g.mailbox("save_seq")) for g in games])
            got = tuple(g.mailbox("self_presence").character for g in games)
            run.expect(got == (ca, cb), f"{pair}: each game plays its pick", got=got)
            for g in games:
                g.write(SUBWEAPON, 1)  # the dagger (Maria: her first guardian)
                g.write(HEARTS, 50, "<i")
            s0 = [g.snapshot() for g in games]
            pads = ["left"] * 90 + ["left+cross"] * 6 + [""] * 40 + ["up+square"] * 3 + [""] * 60
            for p in pads:
                run.step(1, p1=(p, p))
            s1 = [g.snapshot() for g in games]
            for k, g in enumerate(games):
                name = f"{'AB'[k]} ({NAMES[(ca, cb)[k]]})"
                moved = s1[k]["world_x"] < s0[k]["world_x"] - 20 or s1[k]["room"] != s0[k]["room"]
                run.expect(moved and s1[k]["hp"] > 0, f"{pair}: {name} moves", before=s0[k], after=s1[k])
                run.expect(g.read(HEARTS, "<i") < 50, f"{pair}: {name} throws a subweapon",
                           hearts=g.read(HEARTS, "<i"))
    after = hashlib.sha1(disc.read_bytes()).hexdigest()
    run.expect(before == after, "the disc is unchanged", sha1=after)


def as_characters(run, ca, cb):
    """Both games load as these characters (a joint save and its load each)."""
    for g, c in zip((run.s.a, run.s.b), (ca, cb)):
        run.expect(reload_game(run, g), f"{'AB'[g is run.s.b]} loads as {NAMES[c]}")
        run.expect(g.mailbox("self_presence").character == c, f"{'AB'[g is run.s.b]} plays {NAMES[c]}")


def progression(run, ca, cb):
    """M8 criterion 4 (pickups): A finds a relic, B armor, a Life Max Up and a Heart Max Up. Each
    partner gets them all, as with Alucard: +5 max HP and +5 max hearts in both games (M8b §4:
    Richter's vanilla double HP is normalized, and Heart Max Up counts)."""
    from session_progress import (CUBE_OF_ZOE, HEART_VESSEL, HOLY_MAIL, LIFE_VESSEL,
                                  RELIC_CUBE_OF_ZOE, counts, status, take)
    a, b = run.s.a, run.s.b
    as_characters(run, ca, cb)
    take(run, a, CUBE_OF_ZOE)
    run.step(10)
    run.expect(status(a)["relics"][RELIC_CUBE_OF_ZOE] & 1 and status(b)["relics"][RELIC_CUBE_OF_ZOE] & 1,
               f"{NAMES[ca]}'s relic (the Cube of Zoe) is {NAMES[cb]}'s too")
    a0, b0 = status(a), status(b)
    for spot in (HOLY_MAIL, LIFE_VESSEL, HEART_VESSEL):
        take(run, b, spot)
    run.step(10)
    a1, b1 = status(a), status(b)
    run.expect(counts(b1) > counts(b0) and counts(a1) - counts(a0) == counts(b1) - counts(b0),
               f"{NAMES[cb]}'s armor (the Holy Mail) is {NAMES[ca]}'s too", a=counts(a1) - counts(a0),
               b=counts(b1) - counts(b0))
    for k, what in (("hp_max", "max HP"), ("hearts_max", "max hearts")):
        run.expect(a1[k] - a0[k] == 5 and b1[k] - b0[k] == 5, f"+5 {what} in both games",
                   a=a1[k] - a0[k], b=b1[k] - b0[k])


@session_scenario(characters=(CHAR_RICHTER, CHAR_MARIA))
def mixed_party_progression(run):
    """Richter finds the relic, Maria the rest: progression()."""
    progression(run, CHAR_RICHTER, CHAR_MARIA)


@session_scenario(characters=(CHAR_MARIA, CHAR_RICHTER))
def mixed_party_progression_mr(run):
    """Maria finds the relic, Richter the rest (his own vessels): progression()."""
    progression(run, CHAR_MARIA, CHAR_RICHTER)


@session_scenario(characters=(CHAR_RICHTER, CHAR_ALUCARD))
def mixed_party_progression_ra(run):
    """Richter finds the relic, Alucard the rest: progression()."""
    progression(run, CHAR_RICHTER, CHAR_ALUCARD)


@session_scenario(starts=("no1", "entrance"), characters=(CHAR_RICHTER, CHAR_MARIA))
def mixed_party_boss(run):
    """M8 criterion 4 (bosses): Richter (A) walks into the Doppleganger's room, Maria (B) is
    pulled in, both hurt it, it dies once and the kill is recorded in both worlds."""
    from link.mailbox import BOSS
    from session_m5 import bosses, into_boss_room, toward, wait_pulled
    from session_scenarios import heal
    a, b = run.s.a, run.s.b
    as_characters(run, CHAR_RICHTER, CHAR_MARIA)
    run.expect(into_boss_room(run, a) is not None, "Richter is in the boss fight")
    run.expect(wait_pulled(run, b, a, 300) is not None, "Maria was pulled in")
    run.step(30)
    slot = next(iter(bosses(a)))
    hit_by = set()
    for i in range(3600):
        before = bosses(a).get(slot, (0, 0, 0))[1]
        who = (i // 300) % 2
        g = a if who == 0 else b
        pad = toward(g, a, slot, i)
        run.step(1, p1=(pad, "") if who == 0 else ("", pad))
        if i % 20 == 0:
            heal(a), heal(b)
        after = bosses(a).get(slot, (0, 0, 0))[1]
        if after < before:
            hit_by.add(NAMES[(CHAR_RICHTER, CHAR_MARIA)[who]])
        if slot not in bosses(a) or after <= 0:
            break
        if len(hit_by) == 2:
            a.write(a.entity(slot), 1, "<h", 0x3E)  # both have hit it: finish it (harness shortcut)
    run.expect(hit_by == {"Richter", "Maria"}, "both hurt the boss", hit_by=sorted(hit_by))
    for i in range(1800):
        run.step(1)
        if not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & BOSS:
            break
    run.step(120)
    rec = lambda g: [g.read("g_Settings", "<i", 0x30 + 4 * k) for k in range(32)]
    run.expect(any(rec(a)) and rec(a) == rec(b), "the kill is recorded in both worlds")


@session_scenario(starts=("no0", "entrance"), characters=(CHAR_MARIA, CHAR_RICHTER))
def mixed_party_cutscene(run):
    """M8 criterion 4 (cutscenes): Maria (A) walks into the room where Alucard first meets Maria:
    the world sees Alucard, so the scene plays; Richter (B) is pulled in and sees it too."""
    from bots import walker
    from link.mailbox import CUTSCENE
    from session_m5 import LEFT_OF_MARIA, NO0
    from session_scenarios import assert_converged
    a, b = run.s.a, run.s.b
    as_characters(run, CHAR_MARIA, CHAR_RICHTER)
    arrive(run, a, NO0, *LEFT_OF_MARIA)
    bot, started = walker("right", attack_every=0), None
    for i in range(1800):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        if a.mailbox("self_presence").flags & CUTSCENE:
            started = i
            break
    run.expect(started is not None, "Maria's game plays Alucard's cutscene")
    saw = None
    for i in range(1800):
        run.step(1)
        if b.mailbox("self_presence").flags & CUTSCENE:
            saw = i
            break
    run.expect(saw is not None, "Richter's game plays it too")
    for _ in range(3600):
        run.step(1)
        if not (a.mailbox("self_presence").flags | b.mailbox("self_presence").flags) & CUTSCENE:
            break
    run.step(120)
    assert_converged(run)


def mixed_soak(run, ca, cb, minutes):
    """M8 criterion 3 (performance): A and B, as these characters, fight in the hall with random
    input for `minutes`, sharing the room. Measured: frames a game's main loop missed (g_Timer
    falling behind the emulated frames, while in play), each frame's cost as the game sees it
    (GsGetVcount after its drawing: scanlines of the 263 a frame has), and the host's time per
    frame (p99 under 1 ms). Two Alucards miss a few frames in this busy room too; a mixed team
    must not miss more than they do (the caller compares)."""
    from lockstep import random_inputs
    from session_scenarios import assert_converged, heal
    a, b = run.s.a, run.s.b
    for g, c in ((a, ca), (b, cb)):
        if c != CHAR_ALUCARD:
            run.expect(reload_game(run, g), f"{'AB'[g is b]} loads as {NAMES[c]}")
    arrive(run, a, STAGE_NO3, HALL_ROOM_ID, 1300, 200)
    run.step(60)
    arrive(run, b, STAGE_NO3, HALL_ROOM_ID, 1324, 200)
    a.host_ms(), b.host_ms()  # from here
    frames = int(minutes * 3600)
    ia, ib = list(random_inputs(41, frames)), list(random_inputs(42, frames))
    shared = slow = played = 0
    ms, vcount = [], []

    def sample(i, sa, sb):
        if i % 10 == 0:
            vcount.extend(g.read(VCOUNT) for g in (a, b))
    for t in range(0, frames, 600):
        t0 = [g.read("g_Timer") for g in (a, b)]
        run.step(600, p1=lambda i, sa, sb, t=t: (ia[t + i][0], ib[t + i][0]), each=sample)
        for g, before in zip((a, b), t0):
            if g.snapshot()["game_state"] == 2:
                played += 600
                slow += max(0, 600 - (g.read("g_Timer") - before))
        shared += roles(run) in ((ROLE_AUTHORITY, ROLE_GUEST), (ROLE_GUEST, ROLE_AUTHORITY))
        ms += a.host_ms() + b.host_ms()
        heal(a), heal(b)
        p = a.mailbox("self_presence")
        if not roles(run)[0]:
            b.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)
    ms.sort()
    vcount.sort()
    p99 = ms[int(len(ms) * 0.99)] if ms else 0
    numbers = {"dropped": slow, "of": played, "host_p99_ms": round(p99, 3), "shared": shared,
               "scanlines_p50": vcount[len(vcount) // 2], "scanlines_p99": vcount[int(len(vcount) * 0.99)]}
    run.expect(a.snapshot()["game_state"] == 2 and b.snapshot()["game_state"] == 2, "both still in play")
    run.expect(shared >= frames // 600 // 2, "shared most of the time", shared=shared, checks=frames // 600)
    run.expect(p99 < 1.0, "host p99 under 1 ms per frame", **numbers)
    assert_converged(run)
    return numbers



@session_scenario(characters=(CHAR_RICHTER, CHAR_MARIA))
def mixed_soak_10min(run):
    """Richter (A) and Maria (B), 10 minutes, against two Alucards' numbers from
    mixed_soak_baseline_10min (run it first): no more missed frames (within 0.5% of play), p99
    scanlines within 5%."""
    import json
    from coop_env import TOOLS
    mixed = mixed_soak(run, CHAR_RICHTER, CHAR_MARIA, 10)
    base = json.loads((TOOLS["out"] / "mixed_soak_baseline_10min" / "report.json").read_text())
    base = next(c for c in base["checks"] if c["what"].startswith("host p99"))
    run.expect(mixed["dropped"] - base["dropped"] <= mixed["of"] // 200,
               "no more missed frames than two Alucards", mixed=mixed["dropped"], alucards=base["dropped"])
    run.expect(mixed["scanlines_p99"] <= base["scanlines_p99"] * 1.05,
               "each frame costs the game no more than with two Alucards (p99)",
               mixed=mixed["scanlines_p99"], alucards=base["scanlines_p99"])


@session_scenario()
def mixed_soak_baseline_10min(run):
    """Two Alucards: mixed_soak's numbers, for mixed_soak_10min to compare with."""
    mixed_soak(run, CHAR_ALUCARD, CHAR_ALUCARD, 10)


@session_scenario(characters=(CHAR_ALUCARD, CHAR_MARIA))
def mixed_soak_short(run):
    """Alucard (A) and Maria (B): mixed_soak, 2 minutes."""
    mixed_soak(run, CHAR_ALUCARD, CHAR_MARIA, 2)
