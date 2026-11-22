"""M8 session tests (design/M8-maria-and-richter.md): mixed teams in two linked games."""

from session import session_scenario  # first: puts `link` on the path

import hashlib

from link.mailbox import (BUSY, CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW,
                          DEAD, IN_PLAY, PAUSED, ROLE_AUTHORITY, ROLE_GUEST)
from module import COOP_DISC
from session_progress import arrive
from session_shared import roles
import savestates as route

NAMES = {CHAR_ALUCARD: "Alucard", CHAR_RICHTER: "Richter", CHAR_MARIA: "Maria", 3: "Ultimate Maria", 4: "Saturn Maria",
         5: "Ultimate Richter"}
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
    slow = played = 0
    chunks = []  # missed frames in each 600
    together = shared = 0  # samples (every 60 frames) when the room is shareable, and of those, shared
    ms, vcount, chunk_vcount = [], [], []

    def shareable(pa, pb):
        """As module/shared.c's PartnerShareable decides: same room, both in play and free, cameras
        within a screen (CAMERA_NEAR)."""
        free = all(p.flags & IN_PLAY and not p.flags & (BUSY | DEAD | PAUSED) for p in (pa, pb))
        return (free and (pa.stage, pa.room_id) == (pb.stage, pb.room_id)
                and abs(pa.scroll_x - pb.scroll_x) < 256 and abs(pa.scroll_y - pb.scroll_y) < 256)

    def sample(i, sa, sb):
        nonlocal together, shared
        if i % 10 == 0:
            chunk_vcount.extend(g.read(VCOUNT) for g in (a, b))
        if i % 60 == 0:
            pa, pb = a.mailbox("self_presence"), b.mailbox("self_presence")
            if shareable(pa, pb):
                together += 1
                shared += (pa.role, pb.role) in ((ROLE_AUTHORITY, ROLE_GUEST), (ROLE_GUEST, ROLE_AUTHORITY))
    sent_back = False  # #333: the 10 s after the test sends them back to the hall is a load, not play
    for t in range(0, frames, 600):
        t0 = [g.read("g_Timer") for g in (a, b)]
        chunk_vcount.clear()
        run.step(600, p1=lambda i, sa, sb, t=t: (ia[t + i][0], ib[t + i][0]), each=sample)
        if not sent_back:
            vcount.extend(chunk_vcount)
        for g, before in zip((a, b), t0):
            if g.snapshot()["game_state"] == 2 and not sent_back:
                played += 600
                slow += max(0, 600 - (g.read("g_Timer") - before))
                chunks.append(max(0, 600 - (g.read("g_Timer") - before)))
        sent_back = False
        ms += a.host_ms() + b.host_ms()
        heal(a), heal(b)
        # Issue 184: both stay in the hall, whatever the random input does, so the two soaks being
        # compared measure the same room: A back to it if it left, B back beside A
        p = a.mailbox("self_presence")
        if (p.stage, p.room_id) != (STAGE_NO3, HALL_ROOM_ID):
            a.mailbox("command", CMD_ARRIVE, STAGE_NO3, HALL_ROOM_ID, 1300, 200)
            b.mailbox("command", CMD_ARRIVE, STAGE_NO3, HALL_ROOM_ID, 1324, 200)
            sent_back = True
        elif not roles(run)[0]:
            b.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)
            sent_back = True
    ms.sort()
    vcount.sort()
    p99 = ms[int(len(ms) * 0.99)] if ms else 0
    numbers = {"dropped": slow, "of": played, "host_p99_ms": round(p99, 3), "shared": shared, "together": together,
               "scanlines_p50": vcount[len(vcount) // 2], "scanlines_p99": vcount[int(len(vcount) * 0.99)],
               "chunks": chunks}
    run.expect(a.snapshot()["game_state"] == 2 and b.snapshot()["game_state"] == 2, "both still in play")
    samples = frames // 60
    run.expect(together >= samples // 3, "close together in the hall a third of the time or more", together=together, of=samples)
    run.expect(shared >= together * 9 // 10, "sharing the room whenever close (90%)", shared=shared, together=together)
    run.expect(p99 < 1.0, "host p99 under 1 ms per frame", **numbers)
    assert_converged(run)
    return numbers


@session_scenario(characters=(CHAR_RICHTER, CHAR_MARIA), full=True)
def mixed_soak_10min(run):
    """Richter (A) and Maria (B), 10 minutes, against two Alucards' numbers from
    mixed_soak_baseline_10min (run it first): no more missed frames (within 0.5% of play; the
    loads after the test sends them back to the hall aren't play), p99 under 200 scanlines."""
    import json
    from coop_env import TOOLS
    mixed = mixed_soak(run, CHAR_RICHTER, CHAR_MARIA, 10)
    base = json.loads((TOOLS["out"] / "mixed_soak_baseline_10min" / "report.json").read_text())
    base = next(c for c in base["checks"] if c["what"].startswith("host p99"))
    run.expect(mixed["dropped"] - base["dropped"] <= mixed["of"] // 200,
               "no more missed frames than two Alucards", mixed=mixed["dropped"], alucards=base["dropped"])
    # #333: a Richter or Maria body runs their whole player code, more than an Alucard body: the
    # bar is the frame's budget (p99 under 200 of 263 scanlines, as crowd_four_in_the_hall), not 5%
    run.expect(mixed["scanlines_p99"] < 200, "each frame fits with room to spare (p99 under 200 of 263 scanlines)",
               mixed=mixed["scanlines_p99"], alucards=base["scanlines_p99"])


@session_scenario(full=True)
def mixed_soak_baseline_10min(run):
    """Two Alucards: mixed_soak's numbers, for mixed_soak_10min to compare with."""
    mixed_soak(run, CHAR_ALUCARD, CHAR_ALUCARD, 10)


@session_scenario(characters=(CHAR_ALUCARD, CHAR_MARIA))
def mixed_soak_short(run):
    """Alucard (A) and Maria (B): mixed_soak, 2 minutes."""
    mixed_soak(run, CHAR_ALUCARD, CHAR_MARIA, 2)


def partner_graphics_stay_in_their_bank(run, ca, cb):
    """Issue 165: the partner's own graphics loads (Maria's HUD, guardians and font, queued for
    DRA's loader) go to VRAM's second bank. They went to the first, over player 1's HUD name
    (Richter's read MARIA) and sprite sheet. Each game loads its character alone, then they link:
    A's first-bank textures are as they were once B's body runs there."""
    a, b = run.s.a, run.s.b
    a.unlink(), b.unlink()
    for g, c in ((a, ca), (b, cb)):
        if c != CHAR_ALUCARD:
            run.expect(reload_game(run, g), f"{'AB'[g is b]} loads as {NAMES[c]}")
    run.step(120)
    # x 0x200-0x3FF of the first bank: the stage's and enemies' graphics (y 0-0xFF; her guardians
    # went to x 0x300-0x3C0 there) and player 1's sheet and HUD (y 0x100-0x1FF)
    sheet = lambda: a.vram_rect(512, 0, 512, 512)
    before = sheet()
    a.link(), b.link()
    run.step(300)
    run.expect(a.mailbox("partner_age") < 30 and a.mailbox("partner_presence").character == cb,
               f"B's {NAMES[cb]} is with A", age=a.mailbox("partner_age"))
    after = sheet()
    icons = lambda x, y: 0x80 <= x < 0xA0 and 0x180 <= y < 0x1C0  # the pickup icon slots (x 0x280): a shared room's (#354)
    changed = sum(1 for y in range(512) for x in range(512) if before[y][x] != after[y][x] and not icons(x, y))
    run.expect(changed < 200, f"A's own textures are untouched by B's {NAMES[cb]}", pixels_changed=changed)


@session_scenario(characters=(CHAR_RICHTER, CHAR_MARIA))
def partner_graphics_stay_in_their_bank_richter_and_maria(run):
    """Richter (A) with Maria's body in his game: the pairing of the report."""
    partner_graphics_stay_in_their_bank(run, CHAR_RICHTER, CHAR_MARIA)


@session_scenario(characters=(CHAR_ALUCARD, CHAR_MARIA), full=True)
def partner_graphics_stay_in_their_bank_alucard_and_maria(run):
    """Alucard (A) with Maria's body in his game."""
    partner_graphics_stay_in_their_bank(run, CHAR_ALUCARD, CHAR_MARIA)


