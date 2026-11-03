"""Every first-castle room, both players (v1.0, design/M12-v1-release.md part 4; Tucker, 2026-11-02:
"catch any bugs along the way"). One test per area: for each room of the area's stage, both
players arrive on its floor nearest the middle (harness/roommap.py, from the room's collision) and walk right, then left, the way a player crosses it, through whatever
door they reach. Health is topped up: the walk is the test.

Fails on what playtests have hit: a game that stops (the session's crash guard), a load that never
ends, a player bounced back and forth through a door, two authorities or two guests in a room
they share, a partner that stops being heard. Reported, not failed: rooms a bot can't arrive in or
can't leave (a wall, a ledge), and players who end up apart (one fell, one didn't)."""

from session import session_scenario  # first: puts `link` on the path

import roommap
from bots import walker
from link.mailbox import BUSY, CMD_ARRIVE, CUTSCENE, DEAD, IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST
from session_m12 import STARTS

START = str(STARTS / "Boss - Richter.state")  # late in the first castle: its relics, its doors open
HP, HP_MAX = 0x23C, 0x240
WALK = 300            # frames each way
LOAD_LIMIT = 600      # a load (BUSY, no scene) longer than this is stuck
SPLIT_ROLES = 30      # two authorities or two guests in one room this long: they disagree
STALE = 120           # frames without hearing the partner
# Doors a lone Alucard goes back and forth through too: the next room's edge is a wall at the
# door's height (issue 140: the original game's layout, to be checked on a real copy).
KNOWN_LOOPS = {(0x09, 35, 27): "issue 140"}
AREAS = {"no3": 0x41, "np3": 0x07, "no0": 0x00, "no1": 0x01, "lib": 0x02, "cat": 0x03, "no2": 0x04, "chi": 0x05,
         "dai": 0x06, "cen": 0x08, "no4": 0x09, "are": 0x0A, "top": 0x0B, "nz0": 0x0C, "nz1": 0x0D, "dre": 0x12}




def _alive(g):
    g.write("g_Status", g.read("g_Status", "<i", HP_MAX), "<i", HP)


def _arrive(run, g, stage, room_id, x, y, limit=600, pad=""):
    """Sends g there; True once it's in play there. It goes through a load even into the room it's
    in, so it waits for the load to start first (else it would count a room it hadn't left yet)."""
    g.mailbox("command", CMD_ARRIVE, stage, room_id, x, y)
    pads = (pad, "") if g is run.s.a else ("", pad)
    started = False
    for _ in range(limit):
        run.step(1, p1=pads)
        _alive(g)
        p = g.mailbox("self_presence")
        started = started or bool(p.flags & BUSY)
        if started and p.stage == stage and p.room_id == room_id and p.flags & IN_PLAY and not p.flags & BUSY:
            return True
    return False


def crawl_room(run, stage, room, problems, notes):
    a, b = run.s.a, run.s.b
    room_id = room.room_id
    where = f"room {room_id // 8} ({room.left},{room.top})"
    spot = room.spot_near(room.w // 2, room.h // 2)
    if spot is None:
        notes.append(f"{where}: no floor to stand on (a shaft)")
        return
    if not _arrive(run, a, stage, room_id, *spot):
        notes.append(f"{where}: A couldn't arrive")
        return
    run.step(60)
    p = a.mailbox("self_presence")
    if not _arrive(run, b, p.stage, p.room_id, p.ground_x + 16, p.ground_y):
        notes.append(f"{where}: B couldn't arrive next to A")
    seen = ([], [])
    busy = [0, 0]
    split = stale = 0
    for phase, way in enumerate(("right", "left")):
        bots = (walker(way, attack_every=24), walker(way, attack_every=24))
        for t in range(WALK):
            run.step(1, p1=tuple(bots[k](g.snapshot(), t) for k, g in enumerate((a, b))))
            pres = []
            for k, g in enumerate((a, b)):
                _alive(g)
                q = g.mailbox("self_presence")
                pres.append(q)
                scene = g.read("g_CutsceneHasControl")
                busy[k] = busy[k] + 1 if q.flags & BUSY and not scene else 0
                if busy[k] == LOAD_LIMIT:
                    problems.append(f"{where}: {'AB'[k]} stuck in a load for {LOAD_LIMIT} frames ({walker and way})")
                if q.flags & IN_PLAY and not q.flags & BUSY:
                    here = (q.stage, q.room_left, q.room_top)
                    if not seen[k] or seen[k][-1][0] != here:
                        seen[k].append((here, run.s.a.read("g_Timer"), phase))
            pa, pb = pres
            same = (pa.stage, pa.room_left, pa.room_top) == (pb.stage, pb.room_left, pb.room_top)
            both = pa.flags & pb.flags & IN_PLAY and not (pa.flags | pb.flags) & BUSY
            if same and both and pa.role == pb.role and pa.role in (ROLE_AUTHORITY, ROLE_GUEST):
                split += 1
                if split == SPLIT_ROLES:
                    problems.append(f"{where}: both games {'authority' if pa.role == ROLE_AUTHORITY else 'guest'} "
                                    f"in room {pa.room_left},{pa.room_top} for {SPLIT_ROLES} frames")
            else:
                split = 0
            stale = stale + 1 if a.mailbox("partner_age") > 30 else 0
            if stale == STALE:
                problems.append(f"{where}: A stopped hearing B")
    known = KNOWN_LOOPS.get((stage, room.left, room.top))
    for k, s in enumerate(seen):
        # through a side door and straight back, walking one way (the doorway loop of report 221050);
        # up and back down is a jump across a room's top edge, as alone
        flips = [i for i in range(1, len(s) - 1)
                 if s[i + 1][0] == s[i - 1][0] and s[i + 1][2] == s[i][2] and s[i + 1][1] - s[i][1] < 90
                 and s[i][0][2] == s[i - 1][0][2]]
        if len(flips) >= 2 and known:
            notes.append(f"{where}: {'AB'[k]} went back and forth through the door ({known})")
        elif len(flips) >= 2:
            problems.append(f"{where}: {'AB'[k]} bounced through a door {len(flips)} times: {[r for r, _, _ in s][:6]}")
    ra, rb = [r for r, _, _ in seen[0]], [r for r, _, _ in seen[1]]
    if ra and rb and ra[-1] != rb[-1]:
        notes.append(f"{where}: ended apart, A in {ra[-1]}, B in {rb[-1]}")
    if len(ra) <= 1:
        notes.append(f"{where}: A didn't leave the room")


def crawl(run, area):
    stage = AREAS[area]
    problems, notes = [], []
    rooms = roommap.rooms(area)
    for room in rooms:
        crawl_room(run, stage, room, problems, notes)
    print(f"{area}: {len(rooms)} rooms", flush=True)
    for n in notes:
        print("  note:", n, flush=True)
    run.expect(not problems, f"{area}: every room crossed together with no stuck load, door loop or split",
               problems=problems, notes=len(notes))


# The inverted castle (v1.1, issue 47): from the Galamoth start, which has its relics and its doors.
INVERTED_START = str(STARTS / "Boss - Galamoth.state")
INVERTED = {"rno0": 0x20, "rno1": 0x21, "rcat": 0x23, "rno2": 0x24, "rchi": 0x25, "rdai": 0x26, "rcen": 0x28,
            "rno4": 0x29, "rtop": 0x2B, "rnz0": 0x2C, "rnz1": 0x2D}  # (RLIB, RNO3, RARE: no room table extracted)
AREAS.update(INVERTED)


def _register(area):
    def test(run):
        crawl(run, area)
    test.__name__ = f"crawl_{area}"
    test.__doc__ = f"Every room of {area.upper()}, both players walking through it together."
    start = INVERTED_START if area in INVERTED else START
    session_scenario(starts=(start, start), full=True)(test)


for _area in AREAS:
    _register(_area)






@session_scenario(starts=(START, START))
def scene_pull_ignores_a_partner_mid_load(run):
    """Both start in Richter's scene. A teleports to the Royal Chapel; then B leaves the scene by
    teleport to A. B's presence mid-load was half old and half new (the scene's flag, the new
    stage, a position of (0, 4)), and A was pulled there: its room change then hung on a graphics
    load (kind 0xFFFE) for good. Found by crawl_dai. Now A stays in play throughout."""
    a, b = run.s.a, run.s.b
    room = roommap.rooms("dai")[0]
    spot = room.spot_near(room.w // 2, room.h // 2)
    run.expect(_arrive(run, a, AREAS["dai"], room.room_id, *spot), "A arrives in the Royal Chapel")
    run.step(60)
    p = a.mailbox("self_presence")
    b.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x + 16, p.ground_y)
    busy = 0
    for _ in range(400):
        run.step(1)
        busy += bool(a.mailbox("self_presence").flags & BUSY)
    q, r = a.mailbox("self_presence"), b.mailbox("self_presence")
    run.expect(busy == 0, "A is never sent through a load while B arrives", busy_frames=busy, a=str(q))
    run.expect((q.stage, q.room_id) == (r.stage, r.room_id) and r.flags & IN_PLAY and not r.flags & BUSY,
               "B arrives next to A", a=str(q), b=str(r))

