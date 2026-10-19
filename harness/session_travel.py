"""M3 acceptance tests: teleport, respawn, pause rules, joint save (design/M3-teleport-respawn-save.md)."""

import tempfile
from pathlib import Path

from session import Session, session_scenario  # first: puts `link` on the path

from bots import walker
from link.jointsave import JointSave, read_session, save_room
from link.mailbox import BUSY, DEAD, IN_PLAY
from lockstep import random_inputs
from module import COOP_DISC
from session_progress import arrive, status

STAGES = ("entrance", "nz0", "no0", "no1")
ENGINE_NORMAL, ENGINE_MENU, ENGINE_MAP = 1, 2, 20
GAME_PLAY, GAME_OVER = 2, 3


def wait_arrived(run, g, target, limit=600):
    """Steps until g is in play, not busy, in target's (stage, room). Returns frames, or None."""
    for i in range(limit):
        run.step(1)
        p = g.mailbox("self_presence")
        if p.room == target.room and p.flags & IN_PLAY and not p.flags & BUSY:
            return i
    return None


def map_teleport(run, g):
    """Opens g's map, presses ✕ (port 1 of g)."""
    pads = lambda pad: ("", pad) if g is run.s.b else (pad, "")
    run.step(1, p1=pads("select"))
    run.step(40)
    run.step(1, p1=pads("cross"))


@session_scenario(starts=("entrance", "entrance"))
def teleport_map_matrix(run):
    """M3 criteria 1 and 3: for every pair of test stages, B opens the map and presses ✕; B ends
    up in play in A's room, within 16 px of A's last grounded spot, with its status unchanged."""
    results = []
    for sa in STAGES:
        for sb in STAGES:
            with Session(COOP_DISC, starts=(sa, sb)) as s:
                sub = type(run)(s, run.name)
                sub.step(300)  # stage title cards
                a, b = s.a, s.b
                target = a.mailbox("self_presence")
                b0 = status(b)
                map_teleport(sub, b)
                frames = wait_arrived(sub, b, target)
                q = b.mailbox("self_presence")
                near = abs(q.x - target.ground_x) <= 16 and abs(q.y - target.ground_y) <= 16
                same = all(status(b)[k] == b0[k] for k in ("level", "exp", "hp_max", "hand", "body", "relics"))
                results.append((sa, sb, frames, near, same, b.read("g_GameEngineStep")))
    bad = [r for r in results if r[2] is None or not r[3] or not r[4] or r[5] != ENGINE_NORMAL]
    run.expect(not bad, "all 16 map teleports land next to the partner, status unchanged",
               slowest=max(r[2] or 0 for r in results), failures=bad)


@session_scenario(starts=("entrance", "nz0"))
def teleport_partner_busy(run):
    """M3 criterion 3: while A is loading (A itself arriving somewhere), ✕ on B's map does nothing."""
    from link.mailbox import CMD_ARRIVE
    a, b = run.s.a, run.s.b
    run.step(300)
    room0 = b.mailbox("self_presence").room
    run.step(1, p1=("", "select"))
    run.step(40)
    p = b.mailbox("self_presence")
    a.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)  # A starts loading
    for _ in range(3):
        run.step(1)
        if a.mailbox("self_presence").flags & BUSY:
            break
    run.expect(a.mailbox("self_presence").flags & BUSY, "A is busy (loading)")
    run.step(1, p1=("", "cross"))
    run.step(240)
    run.expect(b.mailbox("self_presence").room == room0, "B stayed where it was")


@session_scenario(starts=("entrance", "nz0"))
def teleport_fuzz(run):
    """M3 criterion 2: 200 teleports (map ✕ and commands alternating) while A wanders at random.
    Every one that starts lands B in play within 5 s; no softlock, no crash."""
    from link.mailbox import CMD_ARRIVE
    from session_scenarios import heal
    a, b = run.s.a, run.s.b
    inputs = list(random_inputs(5, 200 * 400))
    t, done, slow, skipped = 0, 0, [], 0
    for n in range(200):
        for _ in range(120):  # A wanders
            run.step(1, p1=(inputs[t][0], "")); t += 1
        target = a.mailbox("self_presence")
        if not target.flags & IN_PLAY or target.flags & (BUSY | DEAD):
            skipped += 1
            continue
        if n % 2:
            map_teleport(run, b)
        else:
            b.mailbox("command", CMD_ARRIVE, target.stage, target.room_id, target.ground_x, target.ground_y)
        for i in range(300):
            run.step(1, p1=(inputs[t][0], "")); t += 1
            q = b.mailbox("self_presence")
            if i > 10 and q.flags & IN_PLAY and not q.flags & BUSY:
                break
        else:
            slow.append((n, str(q)))
        done += 1
        heal(a), heal(b)
    run.expect(done >= 150 and not slow, "every teleport ends in play within 5 s",
               teleports=done, skipped=skipped, stuck=slow[:3])
    run.expect(a.snapshot()["game_state"] == GAME_PLAY and b.snapshot()["game_state"] == GAME_PLAY, "both still in play")


def die(run, g, limit=4000):
    """Harness: HP 1, then walk g into the entrance hall's zombies until the death sequence."""
    g.write("g_Status", 1, "<i", 0x23C)
    bot = walker("left", attack_every=0)
    for i in range(limit):
        pad = bot(g.snapshot(), i)
        run.step(1, p1=(pad, "") if g is run.s.a else ("", pad))
        if g.mailbox("self_presence").flags & DEAD or g.read("g_GameEngineStep") == 10:
            return i
    return None


@session_scenario(starts=("entrance", "nz0"))
def respawn_at_partner(run):
    """M3 criterion 4: A dies in the entrance hall; after the death animation it appears at B
    (in the Alchemy Lab) with full HP, and never reaches Game Over."""
    a, b = run.s.a, run.s.b
    run.step(300)
    t = die(run, a)
    run.expect(t is not None, "A died", frames=t)
    target = b.mailbox("self_presence")
    over = False
    for i in range(900):
        run.step(1)
        over |= a.read("g_GameState") == GAME_OVER
        p = a.mailbox("self_presence")
        if p.room == target.room and p.flags & IN_PLAY and not p.flags & (BUSY | DEAD):
            break
    st = status(a)
    run.expect(not over, "A never reached Game Over")
    run.expect(p.room == target.room, "A reappeared in B's room", a=str(p.room), b=str(target.room))
    run.expect(st["hp"] == st["hp_max"], "with full HP", hp=st["hp"], hp_max=st["hp_max"])
    run.expect(b.snapshot()["game_state"] == GAME_PLAY, "B unaffected")


@session_scenario(starts=("entrance", "entrance"))
def pause_freezes_shared_room(run):
    """M3 criterion 6: B opens its menu in A's room. A's world freezes (player and enemies don't
    move, the RNG holds) while A holds right; when B closes the menu, A moves again. B pausing in
    another room has no effect on A."""
    a, b = run.s.a, run.s.b
    run.step(30)
    run.step(1, p1=("", "start"))
    run.step(60)
    run.expect(b.read("g_GameEngineStep") == ENGINE_MENU, "B is in its menu", engine=b.read("g_GameEngineStep"))
    ents0, x0, rng0 = a.read_bytes("g_Entities", 0xBC * 256), a.snapshot()["world_x"], a.read("g_randomNext")
    run.step(120, p1=("right", ""))
    run.expect(a.snapshot()["world_x"] == x0 and a.read_bytes("g_Entities", 0xBC * 256) == ents0
               and a.read("g_randomNext") == rng0, "A's world is frozen while B is paused")
    for pad in ("triangle", "start", "triangle"):
        if b.read("g_GameEngineStep") == ENGINE_NORMAL:
            break
        run.step(2, p1=("", pad))
        run.step(60)
    run.expect(b.read("g_GameEngineStep") == ENGINE_NORMAL, "B closed its menu", engine=b.read("g_GameEngineStep"))
    run.step(60, p1=("right", ""))
    run.expect(a.snapshot()["world_x"] != x0, "A moves again")
    # Different rooms: A goes elsewhere, B pauses again.
    t = b.mailbox("self_presence")
    arrive(run, a, 0x41, 120, 272, 114)
    run.step(1, p1=("", "start"))
    run.step(60)
    x1 = a.snapshot()["world_x"]
    run.step(60, p1=("left", ""))
    run.expect(a.snapshot()["world_x"] != x1, "B pausing in another room doesn't freeze A")


@session_scenario(starts=("entrance", "entrance"))
def joint_save_and_resume(run):
    """M3 criteria 5 and 7: A saves (a request through the same joint-save path as a save room).
    The session file then holds both saves, B's re-pointed to A's room. Then both die: both reload
    the joint save. Then a fresh boot of both games and 'Continue co-op' puts both in that room,
    each with its own status, and the shared flags and map."""
    path = Path(tempfile.mkdtemp(prefix="coop-session-")) / "session.coop"
    with Session(COOP_DISC, starts=("entrance", "entrance"), session_file=path) as s:
        sub = type(run)(s, run.name)
        a, b = s.a, s.b
        sub.step(30)
        s.joint.request(0)
        for _ in range(120):
            sub.step(1)
            if path.exists():
                break
        run.expect(path.exists(), "the joint save was written", saves=s.joint.saves)
        blobs = read_session(path)
        room_a = a.mailbox("self_presence")
        run.expect(save_room(blobs[0]) == save_room(blobs[1]) == (room_a.stage, room_a.room_left, room_a.room_top),
                   "both saves resume in A's room", a=save_room(blobs[0]), b=save_room(blobs[1]))
        saved = [status(a), status(b)]
        # Both die at once: identical worlds, both at 1 HP, the same walk into the hall's zombies.
        for g in (a, b):
            g.write("g_Status", 1, "<i", 0x23C)
        bots = walker("left", attack_every=0), walker("left", attack_every=0)
        for i in range(4000):
            sub.step(1, p1=(bots[0](a.snapshot(), i), bots[1](b.snapshot(), i)))
            if a.mailbox("self_presence").flags & DEAD and b.mailbox("self_presence").flags & DEAD:
                break
        run.expect(a.mailbox("self_presence").flags & DEAD and b.mailbox("self_presence").flags & DEAD,
                   "both died", frames=i)
        loaded = False
        for i in range(1500):
            sub.step(1)
            pa, pb = a.mailbox("self_presence"), b.mailbox("self_presence")
            if a.read("g_GameState") == GAME_OVER or b.read("g_GameState") == GAME_OVER:
                break
            if i > 240 and pa.flags & IN_PLAY and pb.flags & IN_PLAY and not (pa.flags | pb.flags) & (BUSY | DEAD):
                loaded = True
                break
        run.expect(loaded, "both dead: both reloaded the joint save and are back in play", frames=i)
        run.expect(a.mailbox("self_presence").room == b.mailbox("self_presence").room == room_a.room,
                   "both in the saved room", a=str(a.mailbox("self_presence").room), b=str(b.mailbox("self_presence").room))
        run.expect(status(a)["hp_max"] == saved[0]["hp_max"] and status(b)["level"] == saved[1]["level"],
                   "with their saved status")
    # Fresh boot of both, then Continue co-op.
    with Session(COOP_DISC, starts=(None, None), session_file=path) as s:
        sub = type(run)(s, run.name)
        a, b = s.a, s.b
        sub.step(1800)  # boot to the title screen
        run.expect(a.read("g_GameState") == 1 and b.read("g_GameState") == 1, "both at the title screen")
        s.joint.resume()
        ok = False
        for i in range(3000):
            sub.step(1)
            pa, pb = a.mailbox("self_presence"), b.mailbox("self_presence")
            if pa.flags & IN_PLAY and pb.flags & IN_PLAY and not (pa.flags | pb.flags) & BUSY:
                ok = True
                break
        run.expect(ok, "Continue co-op: both games are in play", frames=i)
        run.expect(pa.room == pb.room == room_a.room, "both in the saved room", a=str(pa.room), b=str(pb.room))
        sa, sb = status(a), status(b)
        run.expect(sa["hp_max"] == saved[0]["hp_max"] and sa["body"] == saved[0]["body"] and
                   sb["hand"] == saved[1]["hand"] and sb["level"] == saved[1]["level"],
                   "each with its own saved status")
        run.expect(a.read_bytes("g_CastleMap", 0x800) == b.read_bytes("g_CastleMap", 0x800), "same map")


def chaos(run, minutes):
    """M3 criterion 8: both games mash buttons; every 10 s one of them teleports to the other,
    and every 30 s one is dropped to 1 HP (so deaths and respawns happen). No crash, both end in
    play, and the shared state converges."""
    from link.mailbox import CMD_ARRIVE
    from session_scenarios import assert_converged
    import random
    a, b = run.s.a, run.s.b
    rng = random.Random(9)
    frames = int(minutes * 3600)
    ia, ib = list(random_inputs(31, frames)), list(random_inputs(32, frames))
    teleports = deaths = 0
    for t in range(0, frames, 600):
        run.step(600, p1=lambda i, sa, sb, t=t: (ia[t + i][0], ib[t + i][0]))
        g, other = (a, b) if rng.random() < 0.5 else (b, a)
        p = other.mailbox("self_presence")
        if p.flags & IN_PLAY and not p.flags & (BUSY | DEAD):
            g.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x, p.ground_y)
            teleports += 1
        if (t // 600) % 3 == 2:
            g.write("g_Status", 1, "<i", 0x23C)
            deaths += 1
        for x in (a, b):
            if x.read("g_GameState") == GAME_OVER:
                run.expect(False, f"game {x.name} reached Game Over", t=t)
    run.step(300)
    run.expect(a.snapshot()["game_state"] == GAME_PLAY and b.snapshot()["game_state"] == GAME_PLAY,
               "both still in play", a=a.snapshot(), b=b.snapshot(), teleports=teleports, low_hp=deaths)
    assert_converged(run)


@session_scenario()
def chaos_short(run):
    chaos(run, 2)


@session_scenario()
def chaos_10min(run):
    chaos(run, 10)
