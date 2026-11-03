#!/usr/bin/env python3
"""Summarizes an unpacked F9 report from its saved game memory: who, where, and how each game stood.

  read_report.py <report folder>... [--map <coop.map>]
"""
import argparse
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESENCE = "<BBBBHHhhhhhHHHIHhhHhhHH"
FLAGS = ["play", "sprite", "paused", "busy", "dead", "boss", "cutscene", "follower"]
ROLES = ["none", "auth", "guest"]
CHARS = ["Alucard", "Richter", "Maria"]


def ram_of(path):
    """A state file's main RAM (research.md: Reading a crash from an F9 report)."""
    data = Path(path).read_bytes()
    at = data.find(b"CPU")
    return data, at + 6702, struct.unpack_from("<36I", data, at + 3 + 8)


def read(data, base, addr, n):
    return data[base + (addr & 0x7FFFFF):base + (addr & 0x7FFFFF) + n]


def presence(raw):
    v = struct.unpack(PRESENCE, raw[:struct.calcsize(PRESENCE)])
    names = "flags character flipX blend stage z left top x y animSet frame_ palette drawFlags frame roomId groundX groundY roomFrames scrollX scrollY role switches".split()
    p = dict(zip(names, v))
    p["flagnames"] = [n for i, n in enumerate(FLAGS) if p["flags"] >> i & 1]
    return p


def describe(p):
    who = CHARS[p["character"]] if p["character"] < 3 else p["character"]
    return (f"{who} stage {p['stage']:#x} room ({p['left']},{p['top']}) xy ({p['x']},{p['y']}) "
            f"ground ({p['groundX']},{p['groundY']}) scroll ({p['scrollX']},{p['scrollY']}) "
            f"role {ROLES[p['role']] if p['role'] < 3 else p['role']} roomFrames {p['roomFrames']} "
            f"{'+'.join(p['flagnames'])}")


def report(folder, syms):
    folder = Path(folder)
    about = json.loads((folder / "about.json").read_text())
    print(f"== {folder.name}: {about.get('note')!r}")
    for name in sorted(folder.glob("before/*.state")) + [folder / "now/A.state"]:
        if not name.exists():
            continue
        data, base, regs = ram_of(name)
        link = syms["g_CoopLink"]
        self_, partner = presence(read(data, base, link + 0xC, 0x2C)), presence(read(data, base, link + 0x38, 0x2C))
        age = struct.unpack("<I", read(data, base, link + 0x64, 4))[0]
        extra = {k: struct.unpack("<I", read(data, base, syms[k], 4))[0]
                 for k in ("g_CoopAfterimagesRepaired", "g_CoopSpikeLines", "g_CoopSpikeMax") if k in syms}
        vec = read(data, base, 0x80, 16).hex()
        print(f" {name.parent.name}/{name.name} pc {regs[34]:08x} vec {vec[:16]} age {age} {extra}")
        print("   me     ", describe(self_))
        print("   partner", describe(partner))
    journal = json.loads((folder / "journal.json").read_text())
    print("  journal", journal[-6:])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("reports", nargs="+")
    ap.add_argument("--map", default=str(ROOT / ".env/out/disc/sotn_coop.us.coop.map"))
    args = ap.parse_args()
    text = Path(args.map).read_text()
    syms = {m[2]: int(m[1], 16) for m in re.finditer(r"^\s+(0x[0-9a-f]{8})\s+(\w+)$", text, re.M)}
    for r in args.reports:
        report(r, syms)
