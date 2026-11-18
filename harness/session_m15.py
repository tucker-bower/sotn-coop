"""M15 (design/M15-pvp.md): PvP, the host's option. The victim's game decides each hit from the
attacker's hitboxes (module/pvp.c, D132); its player's own damage code does the rest."""

from link.mailbox import BUSY, CHAR_ALUCARD, CONTROL_PVP, DEAD, IN_PLAY, OPT_PARTNER_SIM
from module import symbols
from session import session_scenario
from session_progress import status

SUBWEAPON, HEARTS = 0x80097BFC, 0x80097BA8  # g_Status.subWeapon, .hearts

STEP_HIT = 10  # PLAYER.step of a hit reaction (Alucard's, Richter's and Maria's)
SPAWN_SAFE = 180  # pvp.c's SAFE_FRAMES
GAME_OVER = 3  # g_GameState (session_travel.py)


def pvp_hits(g):
    return g.read(symbols()["g_CoopPvpTouches"])


def player_step(g):
    return g.read("g_Entities", "<H", 0x2C)


def apart(run, gap=24):
    """A walks left until it's `gap` px left of B (both start on the same spot; right of it, the
    ground drops)."""
    a, b = run.s.a, run.s.b
    for _ in range(120):
        if b.snapshot()["world_x"] - a.snapshot()["world_x"] >= gap:
            break
        run.step(1, p1=("left", ""))
    run.step(10)
    run.expect(abs(a.snapshot()["world_y"] - b.snapshot()["world_y"]) <= 2, "A and B stand on the same ground",
               a=(a.snapshot()["world_x"], a.snapshot()["world_y"]), b=(b.snapshot()["world_x"], b.snapshot()["world_y"]))


def attack(run, pad, frames=90, every=20, arm=None):
    """A presses `pad` every `every` frames (arm(a) first, each time); returns B's PvP hits, its HP
    drop, the steps it went through and how far it moved."""
    a, b = run.s.a, run.s.b
    hits0, hp0, x0 = pvp_hits(b), status(b)["hp"], b.snapshot()["world_x"]
    steps = set()
    for i in range(frames):
        if arm and i % every == 0:
            arm(a)
        run.step(1, p1=(pad if i % every < 2 else "", ""))
        steps.add(player_step(b))
    return {"hits": pvp_hits(b) - hits0, "hp": hp0 - status(b)["hp"], "steps": sorted(steps),
            "moved": b.snapshot()["world_x"] - x0, "a_body_hits": a.read(symbols()["g_CoopBodyHits"])}


def load_characters(run):
    """Each game loads as its character: the session's applies from a game's next load (a joint
    save and its load, as Continue does), and the start is Alucard's. (Before 2026-10-30 these
    tests didn't, and every "pairing" was two Alucards.)"""
    from session_m8 import reload_game
    from session_progress import arrive
    names = ("Alucard", "Richter", "Maria", "Ultimate Maria", "Saturn Maria", "Ultimate Richter")
    p = run.s.a.mailbox("self_presence")  # both start here; a load puts a player at the save's spot
    for g, c in zip((run.s.a, run.s.b), run.s.characters):
        if c != CHAR_ALUCARD:
            run.expect(reload_game(run, g), f"{'AB'[g is run.s.b]} loads as {names[c]}")
            arrive(run, g, p.stage, p.room_id, p.ground_x, p.ground_y)
            run.step(10)  # arrive() can return before the command starts: the room's load
            while g.mailbox("self_presence").flags & BUSY:
                run.step(1)
    for g, c in zip((run.s.a, run.s.b), run.s.characters):
        run.expect(g.mailbox("self_presence").character == c, f"{'AB'[g is run.s.b]} plays {names[c]}",
                   playing=g.mailbox("self_presence").character)


def setup(run, pvp=True, gap=24, options=0):
    a, b = run.s.a, run.s.b
    load_characters(run)
    for g in (a, b):
        g.mailbox("set_control", CONTROL_PVP if pvp else 0)
        g.host("set_player", options=OPT_PARTNER_SIM | (options if g is a else 0))
    run.step(200)  # past the first 3 s in the room (spawn protection)
    apart(run, gap)
    run.step(1, p1=("right", ""))  # A faces B
    run.step(10)


def expect_hit(run, r, what, away=1):
    run.expect(r["hits"] > 0 and r["hp"] > 0, f"{what} hurt B (B's own damage code)", **r)
    run.expect(STEP_HIT in r["steps"], "B staggered (its hit step)", **r)
    run.expect(r["moved"] * away > 0, f"B was knocked away from A ({'right' if away > 0 else 'left'})", **r)


GALLERY = (0x00, 80, 680, 150)  # NO0, "next to Maria" (debugstarts): flat from x 417 to 693 (her scene is to the right)


@session_scenario(starts=("entrance", "entrance"))
def pvp_off(run):
    """Criterion 3: PvP off (the default), the same swings do nothing."""
    setup(run, pvp=False)
    r = attack(run, "right+square")
    run.expect(r["hits"] == 0 and r["hp"] == 0, "no PvP hit, no HP lost", **r)


@session_scenario(starts=("entrance", "entrance"))
def pvp_spawn_protection(run):
    """Criterion 4: no PvP in a player's first 3 s in a room. A leaves the room and comes back,
    walks up to B and swings at once: nothing. After 3 s in the room, the same swings hurt."""
    a, b = run.s.a, run.s.b
    setup(run)
    room = b.mailbox("self_presence").room
    for _ in range(300):  # out to the left...
        run.step(1, p1=("left", ""))
        if a.mailbox("self_presence").room != room:
            break
    run.expect(a.mailbox("self_presence").room != room, "A left B's room")
    for _ in range(300):  # ...and back
        run.step(1, p1=("right", ""))
        if a.mailbox("self_presence").room == room and a.snapshot()["world_x"] >= 30:
            break
    for _ in range(120):
        if b.snapshot()["world_x"] - a.snapshot()["world_x"] <= 24:
            break
        run.step(1, p1=("right", ""))
    early = a.mailbox("self_presence").room_frames
    r = attack(run, "right+square", frames=60)
    run.expect(early < SPAWN_SAFE - 60 and r["hits"] == 0 and r["hp"] == 0,
               "A's swings in its first 3 s in the room do nothing", room_frames=early, **r)
    run.step(SPAWN_SAFE)
    expect_hit(run, attack(run, "right+square"), "after 3 s, A's swing")


@session_scenario(starts=("entrance", "entrance"))
def pvp_death(run):
    """Criterion 5: B, at 1 HP, dies to A's swing; it respawns at A with full HP, no Game Over,
    and no XP, gold or items change hands."""
    a, b = run.s.a, run.s.b
    setup(run)
    before = {g: (status(g)["exp"], status(g)["gold"], status(g)["hand"]) for g in (a, b)}
    b.write("g_Status", 1, "<i", 0x23C)
    died = None
    for i in range(240):
        run.step(1, p1=("right+square" if i % 20 < 2 else "", ""))
        if b.mailbox("self_presence").flags & DEAD:
            died = i
            break
    run.expect(died is not None, "B died to A's swing", frames=died, hits=pvp_hits(b))
    over = False
    for _ in range(900):
        run.step(1)
        over |= b.read("g_GameState") == GAME_OVER
        p = b.mailbox("self_presence")
        if p.flags & IN_PLAY and not p.flags & (BUSY | DEAD) and status(b)["hp"] == status(b)["hp_max"]:
            break
    run.step(30)
    run.expect(not over, "B never reached Game Over")
    run.expect(b.mailbox("self_presence").room == a.mailbox("self_presence").room and status(b)["hp"] == status(b)["hp_max"],
               "B is back at A, with full HP", hp=status(b)["hp"], room=str(b.mailbox("self_presence").room))
    after = {g: (status(g)["exp"], status(g)["gold"], status(g)["hand"]) for g in (a, b)}
    run.expect(after == before, "no XP, gold or items changed hands")


