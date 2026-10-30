"""M15 (design/M15-pvp.md): PvP, the host's option. The victim's game decides each hit from the
attacker's hitboxes (module/pvp.c, D132); its player's own damage code does the rest."""

from link.mailbox import BOSS, BUSY, CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CONTROL_PVP, DEAD, IN_PLAY, OPT_PARTNER_SIM
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
    run.expect(a.snapshot()["world_y"] == b.snapshot()["world_y"], "A and B stand on the same ground",
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


def setup(run, pvp=True, gap=24, options=0):
    a, b = run.s.a, run.s.b
    for g in (a, b):
        g.mailbox("set_control", CONTROL_PVP if pvp else 0)
        g.host("set_player", options=OPT_PARTNER_SIM | (options if g is a else 0))
    run.step(200)  # past the first 3 s in the room (spawn protection)
    apart(run, gap)
    run.step(1, p1=("right", ""))  # A faces B
    run.step(10)


def expect_hit(run, r, what):
    run.expect(r["hits"] > 0 and r["hp"] > 0, f"{what} hurt B (B's own damage code)", **r)
    run.expect(STEP_HIT in r["steps"], "B staggered (its hit step)", **r)
    run.expect(r["moved"] > 0, "B was knocked away from A (right)", **r)


def _hand(run):
    """Criteria 1-2, a hand attack (weapon, fist, whip): A swings at B. B is hit by its own damage code (its HP drops,
    by less than the attack: its defence), staggers (its hit step) and is knocked away from A;
    A's copy of B shows the hit too."""
    a, b = run.s.a, run.s.b
    setup(run)
    body0 = a.read(symbols()["g_CoopBodyHits"])
    r = attack(run, "right+square")
    run.expect(r["hits"] > 0, "B's game took A's swing", **r)
    run.expect(r["hp"] > 0, "B lost HP", **r)
    run.expect(STEP_HIT in r["steps"], "B staggered (its hit step)", **r)
    run.expect(r["moved"] > 0, "B was knocked away from A (right)", **r)
    run.expect(r["a_body_hits"] > body0, "A's copy of B was hit too", **r)


NAMES = "arm"  # CHAR_ALUCARD, CHAR_RICHTER, CHAR_MARIA


def _pair_test(kind, fn, ca, cb):
    """m15_pvp_<kind>_<A's character><B's>: A (ca) attacks B (cb)."""
    @session_scenario(starts=("entrance", "entrance"), characters=(ca, cb))
    def test(run):
        fn(run)
    test.__name__ = f"m15_pvp_{kind}_{NAMES[ca]}{NAMES[cb]}"
    test.__doc__ = fn.__doc__
    from session import SESSION_SCENARIOS
    SESSION_SCENARIOS[test.__name__] = SESSION_SCENARIOS.pop("test")


@session_scenario(starts=("entrance", "entrance"))
def m15_pvp_off(run):
    """Criterion 3: PvP off (the default), the same swings do nothing."""
    setup(run, pvp=False)
    r = attack(run, "right+square")
    run.expect(r["hits"] == 0 and r["hp"] == 0, "no PvP hit, no HP lost", **r)


def _subweapon(run):
    """Criterion 1, a subweapon: A throws the dagger at B, out of a swing's reach (44 px)."""
    setup(run, gap=44)

    def arm(a):
        a.write(SUBWEAPON, 1, "<i")  # the dagger
        a.write(HEARTS, 50, "<i")
    expect_hit(run, attack(run, "up+square", frames=120, every=40, arm=arm), "A's dagger")


def _spell(run):
    """Criterion 1, a spell: A (Alucard) casts Hellfire (the right-stick shortcut) at B, 44 px away."""
    from link.mailbox import OPT_SHORTCUTS, SPELLS, spell_options
    from scenarios_m8 import MP, MP_MAX, SPELLS_LEARNT
    setup(run, gap=44, options=OPT_SHORTCUTS | spell_options([None, SPELLS.index("Hellfire"), None, None]))

    def arm(a):
        a.write(SPELLS_LEARNT, 0xFF)
        a.write(MP, 99, "<i")
        a.write(MP_MAX, 99, "<i")
    expect_hit(run, attack(run, "rs_right", frames=240, every=120, arm=arm), "A's Hellfire")


# Hand attacks for all 9 pairings; the dagger thrown by Alucard and Richter (Maria's subweapons are
# her guardians); spells are Alucard's.
for _ca in (CHAR_ALUCARD, CHAR_RICHTER, CHAR_MARIA):
    for _cb in (CHAR_ALUCARD, CHAR_RICHTER, CHAR_MARIA):
        _pair_test("hand", _hand, _ca, _cb)
        if _ca != CHAR_MARIA:
            _pair_test("dagger", _subweapon, _ca, _cb)
        if _ca == CHAR_ALUCARD:
            _pair_test("spell", _spell, _ca, _cb)


@session_scenario(starts=("entrance", "entrance"))
def m15_pvp_spawn_protection(run):
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


@session_scenario(starts=("no1", "entrance"))
def m15_pvp_not_in_boss_fight(run):
    """Criterion 4: no PvP in a boss fight. Both in the Doppleganger's room, A swings at B."""
    from session_m5 import into_boss_room, wait_pulled
    a, b = run.s.a, run.s.b
    for g in (a, b):
        g.mailbox("set_control", CONTROL_PVP)
        g.host("set_player", options=OPT_PARTNER_SIM)
    run.expect(into_boss_room(run, a) is not None, "A is in the boss fight")
    run.expect(wait_pulled(run, b, a, 300) is not None, "B was pulled in")
    run.step(SPAWN_SAFE)
    hits0 = pvp_hits(b)
    for i in range(600):
        side = "right" if b.snapshot()["world_x"] > a.snapshot()["world_x"] else "left"
        far = abs(b.snapshot()["world_x"] - a.snapshot()["world_x"]) > 20
        run.step(1, p1=(side if far else (side + "+square" if i % 20 < 2 else ""), ""))
        if i % 30 == 0:
            for g in (a, b):
                g.write("g_Status", status(g)["hp_max"], "<i", 0x23C)
    run.expect(pvp_hits(b) == hits0, "A's swings never hurt B", hits=pvp_hits(b) - hits0,
               boss=bool(b.mailbox("self_presence").flags & BOSS))


@session_scenario(starts=("entrance", "entrance"))
def m15_pvp_not_in_scene(run):
    """Criterion 4: no PvP while a scene has B's game (g_CutsceneHasControl, set by hand here)."""
    a, b = run.s.a, run.s.b
    setup(run)
    for _ in range(90):
        b.write("g_CutsceneHasControl", 1)
        run.step(1, p1=("right+square" if _ % 20 < 2 else "", ""))
    b.write("g_CutsceneHasControl", 0)
    run.expect(pvp_hits(b) == 0 and status(b)["hp"] == status(b)["hp_max"], "A's swings did nothing",
               hits=pvp_hits(b), hp=status(b)["hp"])


@session_scenario(starts=("entrance", "entrance"))
def m15_pvp_death(run):
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


@session_scenario()
def online_pvp_lossy(run):
    """Criterion 6: online, 120 ms round trip and 5% loss each way. A swings at B again and again;
    each swing hits B at most once, and each hit B's game takes (an HP drop) shows once on A's
    copy of B: none lost, none twice."""
    a, b = run.s.a, run.s.b
    run.s.set_net("country", 6, delay=60, jitter=4, loss=0.05)
    setup(run)
    body0 = a.read(symbols()["g_CoopBodyHits"])
    seen = {"drops": 0, "hp": status(b)["hp"]}

    def watch(*_):  # every frame: B's HP drops (hits taken)
        now = status(b)["hp"]
        seen["drops"] += now < seen["hp"]
        seen["hp"] = now
    last_swing, swings = -999, 0
    for i in range(1500):
        dx = b.snapshot()["world_x"] - a.snapshot()["world_x"]
        if dx > 22:
            pad = "right"
        elif i - last_swing >= 60:
            pad, last_swing, swings = "right+square", i, swings + 1
        else:
            pad = ""
        run.step(1, p1=(pad, ""), each=watch)
        if seen["hp"] < status(b)["hp_max"] // 3:
            run.step(60, each=watch)  # A's copy of B gets the hit first...
            b.write("g_Status", status(b)["hp_max"], "<i", 0x23C)
            seen["hp"] = status(b)["hp_max"]
            run.step(60, each=watch)  # ...then the heal, which isn't a hit
    run.step(60, each=watch)
    drops = seen["drops"]
    shown = a.read(symbols()["g_CoopBodyHits"]) - body0
    run.expect(drops >= 5, "A hit B again and again over the lossy link", hits=drops)
    run.expect(drops <= swings, "no swing hit B twice (a lost packet never leaves an attack behind)",
               hits=drops, swings=swings)
    run.expect(shown == drops, "A's copy of B showed each hit once", b_hits=drops, a_shown=shown)


@session_scenario(starts=("entrance", "entrance"))
def m15_pvp_familiar(run):
    """Criterion 1, a familiar: B has the Sword familiar out and walks into the zombie hall,
    pressing nothing else, with A just behind it. The sword fights the zombies; when its attacks
    catch A, they count."""
    from session_m8 import reload_game
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    b.write(0x80097964 + 22, 3, "<B")  # the sword card, on (g_Status.relics)
    run.expect(reload_game(run, b), "B reloads with the sword card on")
    for g in (a, b):
        g.mailbox("set_control", CONTROL_PVP)
        g.host("set_player", options=OPT_PARTNER_SIM)
    into_hall(run)
    run.step(SPAWN_SAFE)
    t0 = pvp_hits(a)
    for i in range(1800):  # B walks into the zombies (pressing nothing else), A just behind it
        sa, sb = a.snapshot(), b.snapshot()
        run.step(1, p1=("left" if sa["world_x"] > sb["world_x"] + 12 else "", "left" if i % 240 < 200 else ""))
        if i % 20 == 0:
            for g in (a, b):
                g.write("g_Status", status(g)["hp_max"], "<i", 0x23C)
        if pvp_hits(a) > t0:
            break
    run.expect(pvp_hits(a) > t0, "the Sword familiar's attacks reached A", frames=i, touches=pvp_hits(a) - t0,
               rooms=(str(a.mailbox("self_presence").room), str(b.mailbox("self_presence").room)))


@session_scenario()
def online_pvp_setting(run):
    """The host's PvP setting covers the session: it goes to the joiner in every HELO, where the
    launcher reads it (launcher/app.py's join_online) to set the joiner's game the same."""
    a, b = run.s.a, run.s.b
    run.step(90)
    run.expect(not (b.host("status").get("partner_hello") or {}).get("pvp"), "off by default")
    a.host("set_pvp", True)
    run.step(90)
    run.expect((b.host("status").get("partner_hello") or {}).get("pvp") is True, "the joiner hears PvP is on",
               hello=b.host("status").get("partner_hello"))
