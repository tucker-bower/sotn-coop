"""Debug starts: savestates to start anywhere on the route, made on the player's PC from their
own disc (savestates hold game RAM, so they're never shipped: D9, D69).

Made once, by the first-run wizard (about a minute), with the disc and BIOS in use; each start
loads into both games. They live in debug-starts/<disc>@<bios>/ with index.json.
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


def _build(disc, out_dir, queue):
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
        steps = 3 + len(STARTS)
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
        (out / "index.json").write_text(json.dumps(index, indent=1))
        queue.put(("done", steps, steps, str(out)))
    except Exception as exc:  # noqa: BLE001 - reported to the wizard, in words
        import traceback
        queue.put(("error", 0, 0, f"{exc}\n{traceback.format_exc()}"))
        sys.exit(1)


def start(disc, out_dir):
    """Starts making them; returns (process, queue of ("progress"|"done"|"error", step, steps, text))."""
    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(target=_build, args=(str(disc), str(out_dir), queue), daemon=True)
    proc.start()
    return proc, queue


def load(out_dir):
    """{name: {"about", "file", "where"}} for starts already made, or {}."""
    index = Path(out_dir) / "index.json"
    return json.loads(index.read_text()) if index.exists() else {}
