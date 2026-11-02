"""Manual: two games as players run them. Each has its own 60 fps clock in its own thread, with
real UDP through the simulated connection on the wall clock (link/netsim.py), PC hitches and a
screenshot of both screens every second. The runner's tests step the games in turn at about 25
times real speed; this is how the 2026-11-01 playtest's trouble looks at full speed.

    python harness/realtime.py [--seconds 90] [--overclock 150] [--jobs 6] [name ...]

Each run writes .env/out/realtime/<overclock>/<name>/: report.json (what went wrong, per second),
sheet.png (a contact sheet of both screens) and a PNG of each moment it flagged."""

import argparse
import json
import multiprocessing as mp
import os
import random
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("COOP_REALTIME", "1")

from coop_env import TOOLS  # noqa: E402

FRAME = 1 / 60
STARTS = TOOLS["out"].parent / "fixtures" / "debug-starts"
VECTOR, VECTOR_SIZE = 0x80000080, 16
GAME_PLAY = 2
HITCH_EVERY, HITCH_S = 900, 0.137  # frames, seconds: the worst a playtest report showed
STUCK_S, STALL_S = 12, 3


def walker(way, attack=24):
    """Walks, attacks and jumps when it stops getting anywhere; turns round if that fails."""
    last, still, flips = None, 0, 0

    def bot(s, t):
        nonlocal last, still, way, flips
        still = still + 1 if (s["world_x"], s["room"]) == last else 0
        last = (s["world_x"], s["room"])
        if still > 240:
            way, still = ("left" if way == "right" else "right"), 0
        pad = [way]
        if t % attack < 2:
            pad.append("square")
        if still > 12 and t % 30 < 15:
            pad.append("cross")
        return "+".join(pad)
    return bot


def masher(seed):
    """Everything a restless player presses: moves, attacks, shield, subweapons, Start now and then."""
    rng, pad, left = random.Random(seed), "", 0
    chords = ["right", "left", "right+square", "left+square", "cross", "right+cross", "up+square",
              "circle", "down", "down+cross", "triangle", "l1", "r1", "left+cross", "right+circle"]

    def bot(s, t):
        nonlocal pad, left
        if not left:
            pad, left = rng.choice(chords), rng.randint(4, 50)
        left -= 1
        return pad
    return bot


def stay(s, t):
    return "square" if t % 40 < 2 else ""


def there_and_back(way, seconds=25):
    back = "left" if way == "right" else "right"
    go, ret = walker(way), walker(back)
    return lambda s, t: go(s, t) if t % (2 * seconds * 60) < seconds * 60 else ret(s, t)


def boss(name):
    return STARTS / f"Boss - {name}"


# name: (start, characters, bot A, bot B, a .save both load first).
ROUTES = {
    "gate": ("no3_start", (0, 1), lambda: walker("right"), lambda: walker("right"), None),
    "gate_swapped": ("no3_start", (1, 0), lambda: walker("right"), lambda: walker("right"), None),
    "hall_doors": ("entrance", (0, 1), lambda: walker("left"), lambda: walker("left"), None),
    "hall_masher": ("entrance", (0, 1), lambda: masher(1), lambda: masher(2), None),
    "apart_alucard_stays": ("entrance", (0, 1), lambda: stay, lambda: there_and_back("left"), None),
    "apart_richter_stays": ("entrance", (0, 1), lambda: there_and_back("left"), lambda: stay, None),
    "chapel_doors": ("Marble Gallery", (0, 1), lambda: walker("right"), lambda: walker("left"), None),
    "lab_doors": ("Alchemy Laboratory", (0, 1), lambda: walker("right"), lambda: masher(3), None),
    "outer_wall": ("Outer Wall", (1, 0), lambda: walker("right"), lambda: walker("right"), None),
    "boss_slogra": ("Boss - Slogra and Gaibon", (0, 1), lambda: walker("left"), lambda: walker("left"), "Slogra and Gaibon"),
    "boss_doppleganger": ("Boss - Doppleganger10", (0, 1), lambda: walker("left"), lambda: walker("left"), "Doppleganger10"),
    "boss_hippogryph": ("Boss - Hippogryph", (1, 0), lambda: walker("right"), lambda: walker("right"), "Hippogryph"),
    "boss_one_enters": ("Boss - Slogra and Gaibon", (0, 1), lambda: walker("left"), lambda: stay, "Slogra and Gaibon"),
}


class Player(threading.Thread):
    def __init__(self, game, bot, seconds, hitch_seed, out):
        super().__init__(daemon=True)
        self.g, self.bot, self.frames, self.out = game, bot, seconds * 60, out
        self.rng = random.Random(hitch_seed)
        self.log, self.shots, self.late, self.flags, self.error = [], [], 0, [], None
        self.stuck_since = self.stall_since = None

    def flag(self, what, **detail):
        self.flags.append(dict(what=what, frame=len(self.log), game=self.g.name, **detail))
        if len([f for f in self.flags if f["what"] == what]) <= 2:
            try:
                self.g.screenshot().save(self.out / f"{self.g.name}_{len(self.log)}_{what.replace(' ', '_')}.png")
            except Exception:  # noqa: BLE001 - the game may be gone: that's flagged already
                pass

    def sample(self, t, s):
        g = self.g
        p = g.mailbox("self_presence")
        row = dict(t=t, timer=g.read("g_Timer"), state=s["game_state"], stage=p.stage, room=s["room"], x=s["world_x"],
                   y=s["world_y"], hp=s["hp"], role=p.role, busy=bool(p.flags & 8), boss=bool(p.flags & 32), dead=bool(p.flags & 16), rtt=None)
        if self.log:
            last = self.log[-1]
            playing = s["game_state"] == GAME_PLAY and last["state"] == GAME_PLAY
            if playing and row["timer"] == last["timer"] and self.stall_since is None:
                self.stall_since = t
            elif row["timer"] != last["timer"]:
                self.stall_since = None
            if self.stall_since is not None and t - self.stall_since == STALL_S * 60:
                self.flag("game stopped", at=row)
                g.save_state_file(self.out / f"{g.name}_stopped.state")
            same = (row["room"], row["x"], row["y"]) == (last["room"], last["x"], last["y"])
            if not same or not playing:
                self.stuck_since = None
            elif self.stuck_since is None:
                self.stuck_since = t
            elif t - self.stuck_since == STUCK_S * 60:
                self.flag("player stuck", at=row)
        self.log.append(row)

    def run(self):
        g, good = self.g, self.g.read_bytes(VECTOR, VECTOR_SIZE)
        s, deadline = g.snapshot(), time.perf_counter()
        try:
            for t in range(self.frames):
                pad = self.bot(s, t)
                s = g.step(1, pad)
                if t % 30 == 0:
                    self.sample(t, s)
                if t % 60 == 0:
                    if g.read_bytes(VECTOR, VECTOR_SIZE) != good:
                        self.flag("CRASH: exception vector overwritten", t=t)
                        return
                    self.shots.append(g.screenshot())
                if t % HITCH_EVERY == HITCH_EVERY - 1:
                    time.sleep(HITCH_S * self.rng.random())
                deadline += FRAME
                wait = deadline - time.perf_counter()
                if wait > 0:
                    time.sleep(wait)
                else:
                    self.late += 1
                    deadline = time.perf_counter() if wait < -0.1 else deadline
        except Exception as e:  # noqa: BLE001 - a dead game is a result
            self.error = str(e)[-600:]
            self.flag("game died", error=self.error)


def load_save(s, name):
    from link.mailbox import BUSY, CMD_LOAD_SAVE, IN_PLAY
    save = (STARTS / f"Boss - {name}.save").read_bytes()
    for g in s.games:
        g.mailbox("put_save", save)
        g.mailbox("command", CMD_LOAD_SAVE)
    s.step(30)
    for _ in range(3000):
        s.step(1)
        if all(g.mailbox("self_presence").flags & IN_PLAY and not g.mailbox("self_presence").flags & BUSY for g in s.games):
            break
    s.step(60)


def compare(a, b):
    """Rows of both players in the same room: their roles must pair up, and a boss shared."""
    problems = []
    by_t = {r["t"]: r for r in b.log}
    for r in a.log:
        q = by_t.get(r["t"])
        if not q or r["state"] != GAME_PLAY or q["state"] != GAME_PLAY:
            continue
        if r["stage"] == q["stage"] and r["room"] == q["room"]:
            if {r["role"], q["role"]} != {1, 2} and r["t"] > 300:
                problems.append(dict(what="same room, not shared", t=r["t"], room=r["room"], roles=(r["role"], q["role"])))
            if r["boss"] != q["boss"]:
                problems.append(dict(what="boss in one game only", t=r["t"], room=r["room"]))
    seen, out = {}, []
    for p in problems:
        seen[p["what"]] = seen.get(p["what"], 0) + 1
        if seen[p["what"]] <= 3:
            out.append(p)
    return out, seen


def sheet(a, b, path):
    from PIL import Image
    pairs = [(x, y) for x, y in zip(a.shots, b.shots) if x and y][::3]
    if not pairs:
        return
    w, h, cols = 256, 240, 4
    rows = (len(pairs) + cols - 1) // cols
    im = Image.new("RGB", (cols * (2 * w + 8), rows * (h + 6)), "white")
    for k, (x, y) in enumerate(pairs):
        ox, oy = (k % cols) * (2 * w + 8), (k // cols) * (h + 6)
        im.paste(x.resize((w, h)), (ox, oy))
        im.paste(y.resize((w, h)), (ox + w + 2, oy))
    im.resize((im.width // 2, im.height // 2)).save(path)


def one(name, seconds, overclock):
    from module import COOP_DISC
    from session import Session
    start, characters, bot_a, bot_b, save = ROUTES[name]
    out = TOOLS["out"] / "realtime" / overclock / name
    out.mkdir(parents=True, exist_ok=True)
    starts = str(STARTS / f"{start}.state") if " " in start else start
    with Session(COOP_DISC, starts=(starts, starts), characters=characters) as s:
        s.set_net("playtest", 1)
        if save:
            load_save(s, save)
        elif start != "no3_start":  # characters come with a load
            from session import SessionRun
            from session_m8 import as_characters
            as_characters(SessionRun(s, name), *characters)
        a, b = Player(s.a, bot_a(), seconds, 1, out), Player(s.b, bot_b(), seconds, 2, out)
        a.start(), b.start()
        a.join(seconds + 30), b.join(seconds + 30)
        problems, counts = compare(a, b)
        speed = []
        for p in (a, b):
            d = [(y["timer"] - x["timer"]) / 30 for x, y in zip(p.log, p.log[1:]) if x["state"] == y["state"] == GAME_PLAY and x["room"] == y["room"]]
            speed.append(dict(mean=round(sum(d) / max(1, len(d)), 3), worst=round(min(d, default=1), 3), late=p.late,
                              rooms=sorted({(r["stage"], *r["room"]) for r in p.log})))
        net = [g.transport("wan_stats") for g in s.games]
        rep = dict(name=name, overclock=overclock, flags=a.flags + b.flags, problems=problems, counts=counts,
                   speed=speed, bytes=[n["bytes_sent"] for n in net], end=[p.log[-1] if p.log else None for p in (a, b)],
                   log=[a.log, b.log])
        (out / "report.json").write_text(json.dumps(rep, indent=0, default=str))
        sheet(a, b, out / "sheet.png")
        return {k: rep[k] for k in ("name", "overclock", "flags", "counts", "speed", "bytes")}


def run_one(args):
    name, seconds, overclock = args
    env = dict(os.environ, COOP_OVERCLOCK=overclock, COOP_REALTIME="1")
    code = f"import sys; sys.path.insert(0,'harness'); import realtime, json; print('RESULT'+json.dumps(realtime.one({name!r},{seconds},{overclock!r}),default=str))"
    try:
        p = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=seconds + 240)
    except subprocess.TimeoutExpired:
        return dict(name=name, overclock=overclock, flags=[dict(what="run timed out")], counts={}, speed=[], bytes=[])
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            return json.loads(line[6:])
    return dict(name=name, overclock=overclock, flags=[dict(what="run failed", tail=p.stderr[-500:])], counts={}, speed=[], bytes=[])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--seconds", type=int, default=90)
    ap.add_argument("--overclock", default="150,200")
    ap.add_argument("--jobs", type=int, default=6)
    o = ap.parse_args()
    jobs = [(n, o.seconds, c) for c in o.overclock.split(",") for n in (o.names or ROUTES)]
    with mp.get_context("spawn").Pool(o.jobs) as pool:
        for r in pool.imap_unordered(run_one, jobs):
            sp = " ".join(f"{x['mean']}/{x['worst']}/late{x['late']}" for x in r["speed"])
            print(f"{r['overclock']:>4} {r['name']:22} speed {sp}  MB {[round(b / 1e6, 1) for b in r['bytes']]}  {r['counts']}", flush=True)
            for f in r["flags"]:
                print(f"       {f['what']} {f.get('game', '')} frame {f.get('frame', '')} {str(f.get('at', f.get('error', f.get('tail', ''))))[:200]}", flush=True)


if __name__ == "__main__":
    main()
