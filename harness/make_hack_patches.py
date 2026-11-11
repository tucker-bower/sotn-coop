"""Makes patcher/mods/hacks.json: the SOTN Editor hacks we've tested with co-op, as the bytes each
writes, so the launcher can put them on a player's disc without the editor (design/launcher-
overhaul.md). Run it after the pinned editor (mods.SOURCES) or the tested list changes.

    python harness/make_hack_patches.py

Each hack is built alone by the editor's own code (editor_hacks.js, as mods.py does) on the
retail disc's files, and only the bytes it changes are kept: never the game's. A hack whose tests
haven't passed (its build.json) is left out. Then every hack applied one after another must give
exactly what the editor gives for all of them at once; one that doesn't is left out too.
The hacks are SOTN Editor's code, under its GPL-3.0 licence: licenses/ has it, the README credits it.
"""

import json
import subprocess
import zlib
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "patcher"))
import mods  # noqa: E402

OUT = ROOT / "patcher" / "mods" / "hacks.json"


def retail_files():
    """{path: bytes} of the retail disc's files the editor reads."""
    raw = mods.RETAIL.read_bytes()
    out = {}
    for path, (lba, size) in mods.files(mods.RETAIL).items():
        path = path.split(";")[0]
        if path.endswith(".BIN") or path.startswith("SLUS"):
            out[path] = b"".join(raw[(lba + i) * mods.SECTOR + mods.DATA:(lba + i) * mods.SECTOR + mods.DATA + 2048]
                                 for i in range((size + 2047) // 2048))[:size]
    return out


def editor(files, ids):
    """{path: bytes} of the files the editor changes for those hacks."""
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp, "in"), Path(tmp, "out")
        for path, data in files.items():
            (src / path).parent.mkdir(parents=True, exist_ok=True)
            (src / path).write_bytes(data)
        r = subprocess.run(["node", str(HERE / "editor_hacks.js"), str(mods.source("editor")), str(src), str(dst), ",".join(ids)],
                           capture_output=True, text=True)
        result = json.loads(r.stdout.strip().splitlines()[-1])
        if r.returncode:
            raise RuntimeError(result.get("error", r.stderr))
        return {p: (dst / p).read_bytes() for p in result["changed"]}


def runs(before, after):
    """[[offset, hex, crc32 of what they replace]] of the bytes that differ: only the new ones (and
    a checksum of the old, so a disc another mod changed there is refused, as the editor does)."""
    out, k = [], 0
    while k < len(after):
        if k < len(before) and before[k] == after[k]:
            k += 1
            continue
        start = k
        while k < len(after) and (k >= len(before) or before[k] != after[k]):
            k += 1
        out.append([start, after[start:k].hex(), zlib.crc32(before[start:k])])
    return out


def compose(files, pick, single, groups):
    """{path: bytes} of the files the hacks in pick change, patched as the launcher does."""
    out = {}

    def write(rs_by_file):
        for path, rs in rs_by_file.items():
            data = bytearray(out.get(path, files[path]))
            for offset, hexed, _ in rs:
                data[offset:offset + len(hexed) // 2] = bytes.fromhex(hexed)
            out[path] = bytes(data)
    for h in pick:
        write(single[h]["files"])
    for g in groups:
        chosen = sorted(set(pick) & set(g["ids"]))
        if chosen:
            write(g["subsets"]["+".join(chosen)])
    return {p: d for p, d in out.items() if d != files[p]}


def interacting(files, ids, single):
    """The hacks whose bytes, applied one by one, differ from the editor's all-at-once build (and
    any hack that writes near those bytes)."""
    together = editor(files, ids)
    group = set()
    for path in set(together) | {p for h in single.values() for p in h["files"]}:
        mine = bytearray(files[path])
        writers = {}
        for h in ids:
            for offset, hexed, _ in single[h]["files"].get(path, []):
                mine[offset:offset + len(hexed) // 2] = bytes.fromhex(hexed)
                for k in range(offset - 64, offset + len(hexed) // 2 + 64):
                    writers.setdefault(k, set()).add(h)
        theirs = together.get(path, files[path])
        for k in range(len(mine)):
            if mine[k] != theirs[k]:
                group |= writers.get(k, set())
    return sorted(group)


def catalog():
    """{id: (label, summary)} from the editor's catalog."""
    js = ("global.window=global;require(process.argv[1]+'/extra-hacks-catalog.js');"
          "const f=global.SotnExtraHacks.features;console.log(JSON.stringify((Array.isArray(f)?f:Object.values(f))"
          ".map(x=>[x.id,x.label,x.summary])))")
    r = subprocess.run(["node", "-e", js, str(mods.source("editor"))], capture_output=True, text=True, check=True)
    return {i: (label, summary) for i, label, summary in json.loads(r.stdout)}


def main():
    files = retail_files()
    names = catalog()
    def record(name):  # what its tests found (mods.built() hides it once the co-op disc is newer: the record stands)
        p = mods.MODS_DIR / name / "build.json"
        return json.loads(p.read_text()) if p.exists() else {}
    tested = [h for h in mods.EDITOR_HACKS if record(f"editor-{h}").get("tested")]
    print(f"{len(tested)} of {len(mods.EDITOR_HACKS)} hacks have passed their tests")
    out = []
    for h in tested:
        changed = editor(files, [h])
        out.append({"id": h, "label": names[h][0], "summary": names[h][1],
                    "files": {p: runs(files[p], data) for p, data in sorted(changed.items())}})
        print(f"  {h}: {sum(len(r[1]) // 2 for rs in out[-1]['files'].values() for r in rs)} bytes in {len(changed)} files")
    # Hacks that write shared code differently when chosen together (the item hacks, at the pinned
    # editor) can't be patched one by one: they're a group, with a patch for each combination.
    ids = [h["id"] for h in out]
    single = {h["id"]: h for h in out}
    group = interacting(files, ids, single)
    groups = []
    if group:
        print(f"these change shared code together: {group}; a patch for each of their {2 ** len(group) - 1} combinations")
        subsets = {}
        for mask in range(1, 2 ** len(group)):
            chosen = [g for k, g in enumerate(group) if mask >> k & 1]
            changed = editor(files, chosen)
            subsets["+".join(sorted(chosen))] = {p: runs(files[p], d) for p, d in sorted(changed.items())}
        groups.append({"ids": sorted(group), "subsets": subsets})
        for g in group:
            single[g]["files"] = {}  # its bytes are in the group's patches
    # Then every selection must be what the editor makes of it: all of them, and a spread of others
    import random
    rnd = random.Random(227)
    picks = [ids] + [sorted(rnd.sample(ids, rnd.randint(2, len(ids)))) for _ in range(12)] + [sorted(group)] * bool(group)
    for pick in picks:
        if compose(files, pick, single, groups) != {p: d for p, d in editor(files, pick).items()} | {}:
            want = editor(files, pick)
            got = compose(files, pick, single, groups)
            bad = sorted(p for p in set(want) | set(got) if want.get(p, files[p]) != got.get(p, files[p]))
            if bad:
                sys.exit(f"{pick}: one by one differs from the editor in {bad}: not written")
    print(f"{len(picks)} selections, all of them included: patched one by one, each is byte for byte the editor's")
    OUT.parent.mkdir(exist_ok=True)
    about = {"editor": mods.SOURCES["editor"][0], "commit": mods.SOURCES["editor"][1], "author": "pddmergilla",
             "license": "GPL-3.0", "note": "Each hack's new bytes only, made by harness/make_hack_patches.py"}
    OUT.write_text(json.dumps({"about": about, "hacks": out, "groups": groups}, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} hacks, {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
