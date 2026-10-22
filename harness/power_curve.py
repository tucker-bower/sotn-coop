"""M8b criterion 4 (design/M8b-character-balance.md §5): the power curve. At each of the 12 boss
starts (launcher/bossstarts.py: a typical player's level, gear and relics), a bot fights the boss
as Alucard, Richter and Maria, and the time to kill and the damage taken per minute are compared.

    python power_curve.py [--bosses N] [--minutes M]

The bot is the same for all three: walk at the boss, attack when close (□; Richter and Maria
also use their off-hand weapon, ○, which holds the start's weapon), jump now and then. It's
healed when low, and the damage it took is counted. A boss not beaten in M minutes (default 4)
counts by the share of its HP taken. Writes .env/out/power_curve/table.md and report.json.
Each start is made once per disc build (debugstarts, as the launcher does)."""

import argparse
import json
import struct
import sys
import time
from pathlib import Path

import session  # noqa: F401  (puts `link` on the path)
from coop_env import TOOLS
from emu import Emu
from link.adapter import HarnessAdapter
from link.mailbox import (BOSS, BUSY, CHAR_ALUCARD, CHAR_BLOB_ADDR, CHAR_MARIA, CHAR_RICHTER, CMD_ARRIVE,
                          CMD_LOAD_SAVE, CMD_SAVE_NOW, IN_PLAY, OPT_SHORTCUTS, Mailbox)
from module import COOP_DISC, maria_blob, symbols
import savestates as route

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "launcher"))
import bossstarts  # noqa: E402
import debugstarts  # noqa: E402

OUT = TOOLS["out"] / "power_curve"
NAMES = {CHAR_ALUCARD: "Alucard", CHAR_RICHTER: "Richter", CHAR_MARIA: "Maria"}
HP, HP_MAX = 0x80097BA0, 0x80097BA4
BAND = 0.20


def starts():
    """{boss name: .state path}, made for this disc build if they aren't yet."""
    folder = OUT / "starts"
    stamp = f"{COOP_DISC.stat().st_mtime_ns}"
    have = debugstarts.load(folder, stamp)
    if not any(v.get("boss") for v in have.values()):
        print("making the boss starts...", flush=True)
        proc, queue = debugstarts.start(COOP_DISC, folder, stamp)
        while True:
            kind, *rest = queue.get()
            if kind == "error":
                raise RuntimeError(rest[-1])
            if kind == "done":
                break
        proc.join()
        have = debugstarts.load(folder, stamp)
    return {n.removeprefix("Boss: "): folder / v["file"] for n, v in have.items() if v.get("boss")}


def wait(e, cond, frames):
    for _ in range(frames):
        if cond():
            return True
        e.step(1)
    return False


def as_character(e, mb, ch):
    """A joint save and its load with this character (how Continue switches it)."""
    if ch == CHAR_MARIA:
        e.write_bytes(CHAR_BLOB_ADDR, maria_blob())
    mb.set_character(ch)
    mb.set_options(OPT_SHORTCUTS)
    seq, p = mb.save_seq(), mb.self_presence()
    mb.command(CMD_SAVE_NOW, p.stage, 0, p.room_left, p.room_top)
    assert wait(e, lambda: mb.save_seq() != seq, 3000), "the save came"
    mb.put_save(mb.save_out())
    mb.command(CMD_LOAD_SAVE)
    assert wait(e, lambda: e.read("g_GameState") == route.GAME_NOW_LOADING, 600), "the load started"
    playing = lambda: (lambda q: q.flags & IN_PLAY and not q.flags & BUSY)(mb.self_presence())  # noqa: E731
    assert wait(e, lambda: e.read("g_GameState") == route.GAME_PLAY and playing(), 3000), "the load finished"
    e.step(120)  # the module loads their weapons and familiar


def boss_target(e, slot=None):
    """(slot, x, hp, entityId) of the boss: the enemy with the most HP (or that slot), or None."""
    raw = e.read_bytes("g_Entities", 0xBC * 256)
    best = None
    for s in ([slot] if slot is not None else range(64, 256)):
        ent = raw[s * 0xBC:(s + 1) * 0xBC]
        eid = struct.unpack_from("<H", ent, 0x26)[0]
        if not eid or (slot is None and not struct.unpack_from("<H", ent, 0x3C)[0]):
            continue
        hp = struct.unpack_from("<h", ent, 0x3E)[0]
        if (slot is not None or 0 < hp < 32767) and (best is None or hp > best[2]):
            best = (s, struct.unpack_from("<h", ent, 2)[0], hp, eid)
    return best


def records(e):
    """The time attack records: a boss beaten adds one (src/dra: TimeAttackController)."""
    return sum(1 for k in range(32) if e.read("g_Settings", "<i", 0x30 + 4 * k))


def fight(e, mb, ch, limit):
    """(seconds to kill or None, damage taken per minute, share of the boss's HP taken). The
    kill: the boss's entity (the most HP when the fight starts) is gone or at 0 HP, and the game
    recorded it (a new time attack record)."""
    taken, frames = 0, 0
    for _ in range(600):  # the boss comes in
        if boss_target(e):
            break
        e.step(1)
    first = boss_target(e)
    if not first:
        return None
    slot, eid, hp0, recs = first[0], first[3], first[2], records(e)
    killed = False
    while frames < limit:
        now = boss_target(e, slot)
        if not now or now[3] != eid or now[2] <= 0:
            for _ in range(600):  # its death plays out, and the game records it
                e.step(1)
                if records(e) > recs:
                    killed = True
                    break
            break
        target = (now[1], now[2])
        me = e.snapshot()["x"]
        pad = []
        if target:
            dist = target[0] - me
            if abs(dist) > 40:
                pad.append("right" if dist > 0 else "left")
            if abs(dist) < 80:
                if frames % 12 == 0:
                    pad.append("square")
                elif ch != CHAR_ALUCARD and frames % 24 == 6:
                    pad.append("circle")
        if frames % 90 == 45:
            pad.append("cross")
        hp = e.read(HP, "<i")
        e.step(1, "+".join(pad))
        frames += 1
        taken += max(0, hp - e.read(HP, "<i"))
        if e.read(HP, "<i") < e.read(HP_MAX, "<i") // 3:
            route.heal(e)
    now = boss_target(e, slot)
    left = now[2] if now and now[3] == eid else 0
    share = 1.0 if killed else max(0.0, 1 - left / hp0)
    return (frames / 60 if killed else None), taken * 3600 / max(frames, 1), share


def run_one(start, b, ch, minutes):
    with Emu(COOP_DISC) as e:
        e.load_state_file(start)
        mb = Mailbox(HarnessAdapter(e), symbols()["g_CoopLink"])
        as_character(e, mb, ch)
        stage = bossstarts.STAGES[b["stage"]]
        room, x, y = b["check"] or b["arrive"]
        mb.command(CMD_ARRIVE, stage, room, x, y)
        wait(e, lambda: (lambda q: q.stage == stage and q.room_id == room and q.flags & IN_PLAY)(mb.self_presence()), 1500)
        e.step(60)
        for i in range(7200):  # walk in until the fight starts
            if mb.self_presence().flags & BOSS:
                break
            e.step(1, b["walk"])
        if not mb.self_presence().flags & BOSS:
            return None
        return fight(e, mb, ch, int(minutes * 3600))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bosses", type=int, default=99)
    ap.add_argument("--minutes", type=float, default=4)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    files = starts()
    rows, t0 = [], time.time()
    for b in bossstarts.B[:args.bosses]:
        if b["name"] not in files:
            continue
        row = {"boss": b["name"], "level": b["level"]}
        for ch in NAMES:
            try:
                r = run_one(files[b["name"]], b, ch, args.minutes)
            except Exception as exc:  # noqa: BLE001 - one bad run is reported, not fatal
                r = None
                print(b["name"], NAMES[ch], "error:", exc, flush=True)
            row[NAMES[ch]] = r
            print(b["name"], NAMES[ch], r, flush=True)
        rows.append(row)
    lines = ["| Boss | Lv | Alucard: kill s / dmg per min | Richter | Maria |", "|---|---|---|---|---|"]

    def cell(r, base):
        if r is None:
            return "didn't reach it"
        ttk, dpm, share = r
        effective = ttk if ttk else (args.minutes * 60 / max(share, 0.01))  # extrapolated
        text = f"{'%.0f' % ttk if ttk else '>%d (%.0f%% of HP)' % (args.minutes * 60, share * 100)} / {dpm:.0f}"
        if base and base[0] is not None:
            bt = base[0] or (args.minutes * 60 / max(base[2], 0.01))
            ratio = effective / bt
            text += f" ({ratio:.2f}×)" + ("" if abs(ratio - 1) <= BAND else " ⚠")
        return text
    for r in rows:
        lines.append(f"| {r['boss']} | {r['level']} | {cell(r['Alucard'], None)} | {cell(r['Richter'], r['Alucard'])} | "
                     f"{cell(r['Maria'], r['Alucard'])} |")
    (OUT / "table.md").write_text("\n".join(lines) + "\n")
    (OUT / "report.json").write_text(json.dumps({"rows": rows, "seconds": round(time.time() - t0)}, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
