"""Autonomous co-op playtests: two games played by bots for minutes at a time, watched for
anything that looks wrong (Tucker, after playtest 1: "you will have to work through doing some
more of your own playtesting").

    python playtest.py [tour ...] [--minutes N] [--seed S]     tours: entrance nz0 no0 no1 (default: all)

Each tour starts both players at one savestate and cycles through phases:
  together  B follows A around (shared rooms, the same enemies)
  apart     both explore on their own (independent worlds, shared progression)
  regroup   B teleports to A from the map
  hop       A arrives in a random room of the stage (harness shortcut, for coverage); B follows
  risky     no healing: deaths and respawns happen

What's flagged (with a screenshot of both screens when it happens):
  STUCK    a game out of play (loading, a menu...) for over 30 s
  FREEZE   a game's screen hasn't changed for 10 s while in normal play
  DROPPED  events lost to a full ring
  FLAP     shared-room roles changing too often (more than 12 times a minute)
  DESYNC   in a shared room, the guest's enemies differ from the authority's for over 2 s
  DIVERGE  at the end of a tour: castle flags, map or pooled gold differ

Output: .env/out/playtest/<tour>/ with report.json, anomaly shots, contact sheets (both screens
side by side every 10 s), and suspects: whenever both share a room with their cameras in the same
place, the two screens should look alike (but the HUD, and the guest's one-frame lag); the six
moments they differed most are saved as suspect_*.png, to look at first.
"""

import argparse
import hashlib
import json
import random
import struct
import sys
import time

from session import Session  # first: puts `link` on the path

from coop_env import TOOLS
from link.mailbox import BUSY, IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST
from module import COOP_DISC
from session_scenarios import EXCLUDED_FLAGS

TOURS = ("entrance", "nz0", "no0", "no1", "castle")
# The castle tour starts at the entrance and hops between stages, to the arrival points of the
# game's own stage doors (DRA's teleport table): every normal stage of the first castle.
TELEPORTS = 0x800A245C  # RoomTeleport[]: x, y, roomId, unk6, stageId (u16 each)
CASTLE_STAGES = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x41}
PHASES = (("together", 60), ("apart", 45), ("regroup", 15), ("hop", 5), ("regroup", 15), ("together", 45),
          ("risky", 30), ("hop", 5), ("regroup", 15), ("together", 30))
GAME_PLAY, ENGINE_NORMAL = 2, 1
SHEET_EVERY = 600  # frames between contact sheet frames
CHECK_EVERY = 30


class Explorer:
    """Walks one way, jumps when stuck, turns around when it stays stuck, attacks now and then."""

    def __init__(self, rng):
        self.rng, self.dir, self.stuck, self.last_x, self.jump = rng, rng.choice(("left", "right")), 0, None, 0
        self.vertical, self.vertical_left = "", 0  # now and then: up (doors) or down (stairs)

    def __call__(self, s, i):
        if s is None:
            return ""
        self.stuck = self.stuck + 1 if s["world_x"] == self.last_x else 0
        self.last_x = s["world_x"]
        if self.stuck > 240 or self.rng.random() < 1 / 2700:  # keep going: cover ground
            self.dir = "left" if self.dir == "right" else "right"
            self.stuck = 0
        if self.vertical_left:
            self.vertical_left -= 1
        elif self.rng.random() < 1 / 600:
            self.vertical, self.vertical_left = self.rng.choice(("up", "down")), 120
        else:
            self.vertical = ""
        buttons = [self.dir] + ([self.vertical] if self.vertical else [])
        if self.stuck > 10 and not self.jump:
            self.jump = 14
        if self.jump:
            self.jump -= 1
            buttons.append("cross")
        if i % 14 < 2:
            buttons.append("square")
        return "+".join(buttons)


class Follower:
    """Walks toward the partner when in the same room; otherwise explores."""

    def __init__(self, rng):
        self.explore = Explorer(rng)

    def __call__(self, s, partner, i):
        if s is None or partner is None or s["room"] != partner["room"] or s["stage"] != partner["stage"]:
            return self.explore(s, i)
        dx = partner["world_x"] - s["world_x"]
        if abs(dx) < 24:
            return "square" if i % 20 < 2 else ""
        pad = self.explore(dict(s), i).split("+")
        pad[0] = "right" if dx > 0 else "left"
        return "+".join(pad)


def frame_hash(g):
    shot = g.screenshot()
    return None if shot is None else hashlib.md5(shot.tobytes()).hexdigest()


def stage_ids(g, slots=range(64, 160)):
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    return {s: struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0] for s in slots}


class Watch:
    def __init__(self, s, out):
        self.s, self.out = s, out
        self.anomalies, self.sheet = [], []
        self.not_play = [0, 0]
        self.hashes = [(None, 0), (None, 0)]
        self.roles, self.role_changes = None, []
        self.desync = 0
        self.frame = 0
        self.suspects = []  # (differing pixels, frame, A shot, B shot)

    def flag(self, kind, **info):
        from PIL import Image
        name = f"{len(self.anomalies):03d}_{kind}.png"
        a, b = self.s.a.screenshot(), self.s.b.screenshot()
        if a and b:
            img = Image.new("RGB", (a.width + b.width + 4, max(a.height, b.height)))
            img.paste(a, (0, 0))
            img.paste(b, (a.width + 4, 0))
            img.save(self.out / name)
        info.update(kind=kind, frame=self.frame, shot=name)
        self.anomalies.append(info)
        print(f"  ! {kind} at frame {self.frame}: {info}", flush=True)

    def check(self, sa, sb):
        s = self.s
        pres = [s.a.mailbox("self_presence"), s.b.mailbox("self_presence")]
        for k, (g, snap, p) in enumerate(zip(s.games, (sa, sb), pres)):
            in_play = snap["game_state"] == GAME_PLAY and p.flags & IN_PLAY and not p.flags & BUSY
            self.not_play[k] = 0 if in_play else self.not_play[k] + CHECK_EVERY
            if self.not_play[k] == 1800:
                self.flag("STUCK", game="AB"[k], state=snap["game_state"], flags=p.flags)
            if self.frame % 60 == 0:
                h = frame_hash(g)
                old, n = self.hashes[k]
                normal = in_play and g.read("g_GameEngineStep") == ENGINE_NORMAL
                n = n + 1 if (h == old and normal) else 0
                self.hashes[k] = (h, n)
                if n == 10:
                    self.flag("FREEZE", game="AB"[k], stage=hex(snap["stage"]), room=snap["room"])
            if g.mailbox("dropped"):
                self.flag("DROPPED", game="AB"[k], n=g.mailbox("dropped"))
        roles = (pres[0].role, pres[1].role)
        if roles != self.roles:
            self.role_changes = [f for f in self.role_changes if f > self.frame - 3600] + [self.frame]
            if len(self.role_changes) == 13:
                self.flag("FLAP", roles=roles)
            self.roles = roles
        if set(roles) == {ROLE_AUTHORITY, ROLE_GUEST} and pres[0].scroll_x == pres[1].scroll_x and \
                pres[0].scroll_y == pres[1].scroll_y and self.frame % 60 == 0:
            self.compare_screens()
        if set(roles) == {ROLE_AUTHORITY, ROLE_GUEST}:
            auth, guest = (s.a, s.b) if roles[0] == ROLE_AUTHORITY else (s.b, s.a)
            ia, ig = stage_ids(auth), stage_ids(guest)
            diff = sorted(k for k in ia if ia[k] != ig[k])
            self.desync = self.desync + CHECK_EVERY if len(diff) > 2 else 0
            if self.desync == 150:
                self.flag("DESYNC", slots=diff[:8], authority={k: ia[k] for k in diff[:8]},
                          guest={k: ig[k] for k in diff[:8]})
        else:
            self.desync = 0

    def compare_screens(self):
        from PIL import ImageChops
        a, b = self.s.a.screenshot(), self.s.b.screenshot()
        if not (a and b) or a.size != b.size:
            return
        box = (0, 40, a.width, a.height)  # below the HUD
        d = ImageChops.difference(a.crop(box).convert("L"), b.crop(box).convert("L"))
        n = sum(1 for v in d.get_flattened_data() if v > 48)
        self.suspects.append((n, self.frame, a, b))
        self.suspects = sorted(self.suspects, key=lambda t: -t[0])[:6]

    def save_suspects(self):
        from PIL import Image
        for k, (n, frame, a, b) in enumerate(self.suspects):
            img = Image.new("RGB", (a.width + b.width + 4, a.height))
            img.paste(a, (0, 0))
            img.paste(b, (a.width + 4, 0))
            img.save(self.out / f"suspect_{k}_f{frame}_{n}px.png")
        return [(n, frame) for n, frame, _, _ in self.suspects]

    def snap_sheet(self, phase):
        a, b = self.s.a.screenshot(), self.s.b.screenshot()
        if a and b:
            self.sheet.append((a, b, phase, self.frame))

    def save_sheets(self):
        from PIL import Image, ImageDraw
        per = 12
        for n in range(0, len(self.sheet), per):
            chunk = self.sheet[n:n + per]
            w, h = chunk[0][0].width, chunk[0][0].height
            img = Image.new("RGB", ((2 * w + 8) * 2, (h + 12) * ((len(chunk) + 1) // 2)), (40, 40, 40))
            d = ImageDraw.Draw(img)
            for k, (a, b, phase, frame) in enumerate(chunk):
                x, y = (k % 2) * (2 * w + 8), (k // 2) * (h + 12)
                img.paste(a, (x, y + 12))
                img.paste(b, (x + w + 4, y + 12))
                d.text((x + 2, y), f"{phase} f{frame} ({frame // 60}s)", fill=(255, 255, 0))
            img.save(self.out / f"sheet_{n // per:02d}.png")


def stage_doors(g):
    """The arrival points of the game's stage doors in normal first-castle stages."""
    out = []
    for k in range(140):
        x, y, room_id, _, stage = struct.unpack("<5H", g.read_bytes(TELEPORTS + k * 10, 10))
        if stage in CASTLE_STAGES and x and y:
            out.append((stage, room_id, x, y))
    return out


def hop(s, rng, castle=False):
    """A arrives in a random room of its stage, somewhere in the middle (it falls to a floor); on
    the castle tour, half the time at a random stage door instead."""
    from link.mailbox import CMD_ARRIVE
    a = s.a
    if castle and rng.random() < 0.5:
        doors = stage_doors(a)
        if doors:
            a.mailbox("command", CMD_ARRIVE, *rng.choice(doors))
            return
    rooms = a.read(a.addr("g_api") + 16)  # g_api.o.rooms
    table = []
    off = 0
    while len(table) < 200:
        left, top, right, bottom, _, tileset = a.read_bytes(rooms + off, 6)
        if left == 0x40:
            break
        if tileset != 0xFF:  # 0xFF: a stage transition (loading room), not a room
            table.append((off, (right - left + 1) * 256, (bottom - top + 1) * 256))
        off += 8
    if table:
        room_id, w, h = rng.choice(table)
        p = a.mailbox("self_presence")
        a.mailbox("command", CMD_ARRIVE, p.stage, room_id, w // 2, min(h // 2, 160))


def tour(name, minutes, seed):
    from session_scenarios import heal
    out = TOOLS["out"] / "playtest" / name
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    rng = random.Random(seed)
    t0 = time.time()
    start = "entrance" if name == "castle" else name
    with Session(COOP_DISC, starts=(start, start)) as s:
        run = s  # no clip: contact sheets instead (a GIF frame every 12 frames is too slow here)
        w = Watch(s, out)
        ea, fb, eb = Explorer(rng), Follower(rng), Explorer(rng)
        state = {"sa": None, "sb": None}
        total = int(minutes * 3600)
        cycle = sum(n for _, n in PHASES) * 60
        last_phase = None
        while w.frame < total:
            t = w.frame % cycle
            for k, (phase, secs) in enumerate(PHASES):
                if t < secs * 60:
                    break
                t -= secs * 60
            entered = (k, w.frame // cycle) != last_phase  # a phase starts
            last_phase = (k, w.frame // cycle)
            if entered:
                print("  phase", phase, "at", w.frame, "A", hex(s.a.snapshot()["stage"]), s.a.snapshot()["room"], flush=True)
            if phase == "hop" and entered:
                hop(s, rng, castle=name == "castle")
            if phase == "regroup" and entered:
                for pad, n in (("select", 1), ("", 40), ("cross", 1)):
                    run.step(n, p1=("", pad))
                    w.frame += n

            def pads(i, sa, sb):
                sa, sb = sa or state["sa"], sb or state["sb"]
                pa = ea(sa, w.frame + i)
                pb = fb(sb, sa, w.frame + i) if phase in ("together", "regroup", "hop") else eb(sb, w.frame + i)
                return pa, pb

            sa, sb = run.step(CHECK_EVERY, p1=pads)
            state.update(sa=sa, sb=sb)
            w.frame += CHECK_EVERY
            if phase != "risky":
                for g, snap in ((s.a, sa), (s.b, sb)):
                    if snap["hp"] < 30:
                        heal(g)
            w.check(sa, sb)
            if w.frame % SHEET_EVERY < CHECK_EVERY:
                w.snap_sheet(phase)
        run.step(300)  # let the last events land
        fa, fb_ = bytearray(s.a.read_bytes("g_CastleFlags", 0x300)), bytearray(s.b.read_bytes("g_CastleFlags", 0x300))
        for i in EXCLUDED_FLAGS:
            fa[i] = fb_[i] = 0
        diff = [hex(i) for i in range(0x300) if fa[i] != fb_[i]]
        maps = s.a.read_bytes("g_CastleMap", 0x800) == s.b.read_bytes("g_CastleMap", 0x800)
        gold = (s.a.read("g_Status", "<i", 0x28C), s.b.read("g_Status", "<i", 0x28C))
        if diff or not maps or gold[0] != gold[1]:
            w.flag("DIVERGE", flags=diff[:10], maps_equal=maps, gold=gold)
        w.save_sheets()
        suspects = w.save_suspects()
        report = {"tour": name, "minutes": minutes, "seed": seed, "seconds": round(time.time() - t0),
                  "anomalies": w.anomalies, "sheets": len(list(out.glob("sheet_*.png"))),
                  "suspects": suspects}
        (out / "report.json").write_text(json.dumps(report, indent=1))
        print(f"{name}: {len(w.anomalies)} anomalies, {report['sheets']} sheets, suspects {suspects}, "
              f"{report['seconds']} s -> {out}")
        return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tours", nargs="*", default=list(TOURS))
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    reports = [tour(t, args.minutes, args.seed + k) for k, t in enumerate(args.tours)]
    sys.exit(1 if any(r["anomalies"] for r in reports) else 0)


if __name__ == "__main__":
    main()
