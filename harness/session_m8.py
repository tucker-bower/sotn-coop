"""M8 session tests (design/M8-maria-and-richter.md): mixed teams in two linked games."""

from session import session_scenario  # first: puts `link` on the path

from bots import walker
import hashlib

from link.mailbox import (BUSY, CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CMD_LOAD_SAVE, CMD_SAVE_NOW,
                          IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST)
from module import COOP_DISC
from session_progress import arrive
from session_scenarios import partner_pixels
from session_shared import into_hall, roles, stage_entities
import savestates as route

NAMES = {CHAR_ALUCARD: "Alucard", CHAR_RICHTER: "Richter", CHAR_MARIA: "Maria"}
STATUS = 0x80097964  # g_Status (include/game.h)
HEARTS, SUBWEAPON = 0x80097BA8, 0x80097BFC
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
            run.expect(all(reload_game(run, g) for g in games), f"{pair}: both load")
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
