"""Debug starts: savestates to start anywhere on the route, made on the player's PC from their
own disc (savestates hold game RAM, so they're never shipped: D9, D69).

Made once (about a minute), with the disc and BIOS in use; each start
loads into both games. The boss starts (bossstarts.py) come with a typical player's progress. They live in debug-starts/<disc>@<bios>/ with index.json.
"""

import json
import multiprocessing
from pathlib import Path

# name: (what's there, base checkpoint, arrive (stage, room, x, y) or None, walk left to (room) or None)
STARTS = {
    "Castle Entrance": ("Where Death takes the gear", "entrance", None, None),
    "Entrance hall": ("Zombies and Wargs: a shared-room fight", "entrance", None, (14, 40)),
    "Alchemy Laboratory": ("The lab's first room", "nz0", None, None),
    "Alchemy Lab: elevator shaft": ("A tall shaft with an elevator (solid entities)", "nz0", (0x0C, 176, 104, 36), None),
    "Alchemy Lab: save room": ("Next to a save coffin", "nz0", (0x0C, 200, 48, 0xA4), None),
    "Marble Gallery": ("The gallery's first room", "no0", None, None),
    "Marble Gallery: next to Maria": ("Walk right: the first meeting with Maria (a cutscene)", "no0", (0x00, 80, 728, 135), None),
    "Outer Wall": ("The wall's first room", "no1", None, None),
    "Outer Wall: next to the Doppleganger": ("Walk left: the Doppleganger (a boss)", "no1", (0x01, 96, 40, 135), None),
}


def _build(disc, out_dir, queue, patch=None):
    """In a worker process: the emulator core loads once per process."""
    import sys
    try:
        from emu import Emu
        from link.adapter import HarnessAdapter
        from link.mailbox import BUSY, CMD_ARRIVE, IN_PLAY, Mailbox
        from module import symbols
        import savestates as route
        from bots import walker

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        import bossstarts
        steps = 3 + len(STARTS) + 1 + len(bossstarts.B) + len(bossstarts.S)
        queue.put(("progress", 0, steps, "Starting a new game"))
        index = {}
        with Emu(disc) as e:
            mb = Mailbox(HarnessAdapter(e), symbols()["g_CoopLink"])
            route.new_game(e)
            queue.put(("progress", 1, steps, "Skipping the prologue"))
            route.skip_prologue(e)
            queue.put(("progress", 2, steps, "Walking to the castle"))
            route.play_to_death(e)
            bases = {"entrance": e.save_state()}
            for name, stage in route.WARPS.items():
                e.load_state(bases["entrance"])
                route.warp(e, stage)
                bases[name] = e.save_state()
            for k, (name, (about, base, arrive, walk_to)) in enumerate(STARTS.items()):
                queue.put(("progress", 3 + k, steps, name))
                e.load_state(bases[base])
                if arrive:
                    mb.command(CMD_ARRIVE, *arrive)
                    for _ in range(900):
                        e.step(1)
                        p = mb.self_presence()
                        if p.stage == arrive[0] and p.room_id == arrive[1] and p.flags & IN_PLAY and not p.flags & BUSY:
                            break
                    e.step(60)
                if walk_to:
                    bot = walker("left", attack_every=0)
                    for i in range(1500):
                        e.step(1, bot(e.snapshot(), i))
                        if e.snapshot()["room"] == walk_to and i > 200:
                            break
                    e.step(60)
                route.heal(e)
                e.step(1)
                file = name.replace(":", " -") + ".state"
                e.save_state_file(out / file)
                index[name] = {"about": about, "file": file, "where": e.snapshot()}
            queue.put(("progress", 3 + len(STARTS), steps, "Mapping the castle"))
            rooms = _survey(e, bases["entrance"], route, bossstarts)
            for k, b in enumerate(bossstarts.B):
                queue.put(("progress", 4 + len(STARTS) + k, steps, b["name"]))
                name = f"Boss: {b['name']}"
                ok = _boss_start(e, mb, bases["entrance"], b, rooms, bossstarts)
                file = name.replace(":", " -").replace("&", "and") + ".state"
                e.save_state_file(out / file)
                about = bossstarts.about(b) + ("" if ok else " (the check didn't reach the boss)")
                index[name] = {"about": about, "file": file, "where": e.snapshot(), "boss": True, "checked": ok}
            for k, b in enumerate(bossstarts.S):  # scene starts (Tucker, 2026-10-26)
                queue.put(("progress", 4 + len(STARTS) + len(bossstarts.B) + k, steps, b["name"]))
                name = f"Scene: {b['name']}"
                ok = _boss_start(e, mb, bases["entrance"], b, rooms, bossstarts)
                file = name.replace(":", " -").replace("&", "and") + ".state"
                e.save_state_file(out / file)
                about = bossstarts.about(b) + ("" if ok else " (the check didn't reach the scene)")
                index[name] = {"about": about, "file": file, "where": e.snapshot(), "scene": True, "checked": ok}
        # The starts hold the co-op module as it was: made for one patch only.
        (out / "index.json").write_text(json.dumps({"patch": patch, "starts": index}, indent=1))
        queue.put(("done", steps, steps, str(out)))
    except Exception as exc:  # noqa: BLE001 - reported to the wizard, in words
        import traceback
        queue.put(("error", 0, 0, f"{exc}\n{traceback.format_exc()}"))
        sys.exit(1)


def _wait(e, cond, frames):
    for _ in range(frames):
        if cond():
            return True
        e.step(1)
    return False


def _survey(e, entrance, route, bossstarts):
    """{area: map cells}, from each area's own room table (warping there from the entrance)."""
    areas = sorted({a for b in bossstarts.B for a in b["areas"]})
    rooms = {}
    for a in areas:
        e.load_state(entrance)
        if a != "NO3":
            route.warp(e, bossstarts.STAGES[a])
        rooms[a] = bossstarts.survey(e)
    return rooms


def _boss_start(e, mb, entrance, b, rooms, bossstarts):
    """Leaves the emulator outside boss b with b's progress; True if a bot then reached the boss
    (for a scene start, b["scene"]: its scene started)."""
    from link.mailbox import BOSS, BUSY, CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW, CUTSCENE, IN_PLAY
    from bots import walker
    import savestates as route

    e.load_state(entrance)
    bossstarts.apply(e, b, e.read_bytes("g_Status", route.STATUS_SIZE), rooms)
    # A joint save and its load: the game recomputes everything from the status, as after a
    # memory card load.
    seq, p = mb.save_seq(), mb.self_presence()
    mb.command(CMD_SAVE_NOW, p.stage, 0, p.room_left, p.room_top)
    if not _wait(e, lambda: mb.save_seq() != seq, 3000):
        raise RuntimeError(f"{b['name']}: the save never came")
    mb.put_save(mb.save_out())
    mb.command(CMD_LOAD_SAVE)
    playing = lambda: (lambda q: q.flags & IN_PLAY and not q.flags & BUSY)(mb.self_presence())
    if not (_wait(e, lambda: e.read("g_GameState") == route.GAME_NOW_LOADING, 600) and
            _wait(e, lambda: e.read("g_GameState") == route.GAME_PLAY and playing(), 3000)):
        raise RuntimeError(f"{b['name']}: the save didn't load")
    e.step(60)
    stage = bossstarts.STAGES[b["stage"]]
    room, x, y = b["arrive"]
    mb.command(CMD_ARRIVE, stage, room, x, y)
    here = lambda: (lambda q: q.stage == stage and q.room_id == room)(mb.self_presence())
    scene = lambda: mb.self_presence().flags & CUTSCENE  # the Nightmare opens with one
    if not _wait(e, lambda: here() and (playing() or scene()), 1200):
        raise RuntimeError(f"{b['name']}: never arrived: {e.snapshot()}")
    e.step(90)
    route.heal(e)
    e.step(1)
    start = e.save_state()
    if b["check"]:
        mb.command(CMD_ARRIVE, stage, *b["check"])
        _wait(e, lambda: mb.self_presence().x != 0 and playing(), 1200)
        e.step(60)
    bot = walker(b["walk"], attack_every=0)
    ok = False
    for i in range(7200):  # an arena may take a while to bring its boss in; Richter talks first
        if mb.self_presence().flags & (CUTSCENE if b.get("scene") else BOSS):
            ok = True
            break
        e.step(1, bot(e.snapshot(), i))
    e.load_state(start)
    return ok


def start(disc, out_dir, patch=None):
    """Starts making them; returns (process, queue of ("progress"|"done"|"error", step, steps, text)).
    patch: the co-op patch's id (its target CRC), recorded with them."""
    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_build, args=(str(disc), str(out_dir), queue, patch), daemon=True)
    proc.start()
    return proc, queue


def load(out_dir, patch=None):
    """{name: {"about", "file", "where"}} for starts already made with this patch, or {}. Starts
    from another patch would run its co-op module (playtest 2026-10-20: old code came back)."""
    index = Path(out_dir) / "index.json"
    if not index.exists():
        return {}
    data = json.loads(index.read_text())
    if "starts" not in data or data.get("patch") != patch:
        return {}
    return data["starts"]
