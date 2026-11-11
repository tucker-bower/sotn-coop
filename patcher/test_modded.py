"""Game discs with several mods (patcher/modded.py, sectordiff.py, mods/hacks.json), on made-up
images: two mods that change the same byte are refused by name; a sector diff gives back the
image it was made from; the shipped hacks hold none of the game's bytes. With a dev checkout's
retail disc, a real hack goes on and only its files change.

    python patcher/test_modded.py
"""

import json
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import modded  # noqa: E402
import sectordiff  # noqa: E402
import sectors  # noqa: E402
from patcher import DiscError  # noqa: E402

S = sectors.SECTOR
failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def image(n=20):
    """n form 1 data sectors, each sealed, numbered in its data."""
    out = bytearray()
    for i in range(n):
        s = bytearray(S)
        s[0:12] = b"\x00" + b"\xff" * 10 + b"\x00"
        s[15] = 2
        s[24:28] = i.to_bytes(4, "little")
        out += sectors.seal(s)
    return out


def ppf3(writes):
    """A PPF3 patch with no block check: [(offset, bytes)]."""
    out = bytearray(b"PPF30" + bytes([2]) + b"made up".ljust(50) + bytes([0, 0, 0, 0]))
    for offset, data in writes:
        out += offset.to_bytes(8, "little") + bytes([len(data)]) + data
    return bytes(out)


def main():
    retail = bytes(image())
    other = bytearray(retail)
    other[3 * S + 100] = 7
    other[9 * S + 200:9 * S + 210] = b"randomized"
    diff = sectordiff.make(retail, bytes(other))
    check(sectordiff.apply(retail, diff) == bytes(other) and len(diff) < 2 * S, "a sector diff gives back its image, and keeps only what changed")
    try:
        sectordiff.apply(retail, diff[:20])
        check(False, "a damaged diff is refused")
    except sectordiff.DiffError:
        check(True, "a damaged diff is refused")

    a = {"name": "Mod A", "ppf": ppf3([(5 * S + 30, b"AAAA")])}
    b = {"name": "Mod B", "ppf": ppf3([(6 * S + 30, b"BBBB")])}
    clash = {"name": "Mod C", "ppf": ppf3([(5 * S + 31, b"CC")])}
    same = {"name": "Mod D", "ppf": ppf3([(5 * S + 30, b"AA")])}
    got, owner = modded.mod_image(retail, [a, b])
    check(got[5 * S + 30:5 * S + 34] == b"AAAA" and got[6 * S + 30:6 * S + 34] == b"BBBB" and owner == {5: "Mod A", 6: "Mod B"},
          "two mods in different places: both on, each sector known by its mod")
    check(bytes(sectors.seal(bytearray(got[5 * S:6 * S]))) == bytes(got[5 * S:6 * S]), "a sector a mod wrote is sealed again")
    try:
        modded.mod_image(retail, [a, clash])
        check(False, "two mods changing one byte differently are refused")
    except DiscError as e:
        check("Mod C" in str(e) and "Mod A" in str(e), f"two mods changing one byte differently are refused, by name: {e}")
    got, _ = modded.mod_image(retail, [a, same])
    check(got[5 * S + 30:5 * S + 34] == b"AAAA", "a second mod writing the same bytes the same way is fine")
    got, _ = modded.mod_image(retail, [{"name": "Seed", "sectors": diff}, a])
    check(got[9 * S + 200:9 * S + 210] == b"randomized" and got[5 * S + 30:5 * S + 34] == b"AAAA", "a randomized disc's diff, then a patch")

    # The shipped hacks
    table = json.loads(modded.HACKS.read_text())
    ids = [h["id"] for h in table["hacks"]]
    check(len(ids) >= 20 and all(h["label"] and h["summary"] for h in table["hacks"]) and table["about"]["license"] == "GPL-3.0",
          f"{len(ids)} hacks ship, each with its name and what it does, under SOTN Editor's licence")
    grouped = {i for g in table.get("groups", []) for i in g["ids"]}
    check(all(len(g["subsets"]) == 2 ** len(g["ids"]) - 1 for g in table.get("groups", [])),
          f"hacks that change shared code together ({sorted(grouped)}) have a patch for each combination")
    writes = modded.hack_writes(["fast-warp", "quick-items", "mp-items"])
    check("ST/WRP/WRP.BIN" in writes and "DRA.BIN" in writes, "the writes of a choice: each hack's own and its group's for the ones chosen")
    try:
        modded.hack_writes(["no-such-hack"])
        check(False, "an unknown hack is refused")
    except DiscError:
        check(True, "an unknown hack is refused")

    retail_disc = HERE.parent / "disks" / "Castlevania - Symphony of the Night (USA) (Track 1).bin"
    if retail_disc.exists():
        real = retail_disc.read_bytes()
        chunks = set()
        for i in range(0, len(real) - S + 1, S):
            if real[i + 15] == 2 and not real[i + 18] & 0x20:
                d = real[i + 24:i + 24 + 2048]
                chunks.update(d[k:k + 64] for k in range(0, 2048 - 63, 4))
        found = 0
        runs = [r for h in table["hacks"] for rs in h["files"].values() for r in rs] + \
               [r for g in table.get("groups", []) for f in g["subsets"].values() for rs in f.values() for r in rs]
        for _, hexed, *_ in runs:
            data = bytes.fromhex(hexed)
            found += sum(1 for k in range(0, len(data) - 63, 16) if len(set(data[k:k + 64])) > 4 and data[k:k + 64] in chunks)
        check(not found, f"the shipped hacks hold nothing of the retail disc's data ({len(runs)} runs checked)")
        got, owner = modded.mod_image(real, [{"name": "Fast warp", "hacks": ["fast-warp"]}])
        changed = sorted(owner)
        check(changed and set(owner.values()) == {"Fast warp"} and zlib.crc32(got) != zlib.crc32(real),
              f"Fast warp on the real disc: {len(changed)} sectors change, all its own")
        place = modded.patcher.find_file(got, "ST/WRP/WRP.BIN")
        other = bytearray(real)
        at = place[0] * S + 24 + 30832  # a byte Fast Warp changes, changed first by another mod
        other[at] ^= 0xFF
        try:
            modded.mod_image(bytes(other), [{"name": "Fast warp", "hacks": ["fast-warp"]}])
            check(False, "a hack on a disc another mod changed where it patches is refused")
        except DiscError as e:
            check("Fast Warp" in str(e) and "original game" in str(e), f"a hack on a disc another mod changed where it patches is refused: {e}")
        del other
        del real, got
    else:
        print("     (no retail disc here: the real checks are skipped)")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
