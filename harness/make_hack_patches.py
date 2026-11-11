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
    """[[offset, hex]] of the bytes that differ: only the new ones."""
    out, k = [], 0
    while k < len(after):
        if k < len(before) and before[k] == after[k]:
            k += 1
            continue
        start = k
        while k < len(after) and (k >= len(before) or before[k] != after[k]):
            k += 1
        out.append([start, after[start:k].hex()])
    return out


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
    tested = [h for h in mods.EDITOR_HACKS if mods.built(f"editor-{h}").get("tested")]
    print(f"{len(tested)} of {len(mods.EDITOR_HACKS)} hacks have passed their tests")
    out = []
    for h in tested:
        changed = editor(files, [h])
        out.append({"id": h, "label": names[h][0], "summary": names[h][1],
                    "files": {p: runs(files[p], data) for p, data in sorted(changed.items())}})
        print(f"  {h}: {sum(len(r[1]) // 2 for rs in out[-1]['files'].values() for r in rs)} bytes in {len(changed)} files")
    # One after another must be what the editor makes of them all at once
    together = editor(files, [h["id"] for h in out])
    ours = dict(files)
    for h in out:
        for path, rs in h["files"].items():
            data = bytearray(ours[path])
            for offset, hexed in rs:
                data[offset:offset + len(hexed) // 2] = bytes.fromhex(hexed)
            ours[path] = bytes(data)
    differ = sorted(p for p in set(together) | {p for h in out for p in h["files"]} if ours[p] != together.get(p, files[p]))
    if differ:
        sys.exit(f"applied one by one, the hacks differ from the editor's all-at-once build in {differ}: not written")
    OUT.parent.mkdir(exist_ok=True)
    about = {"editor": mods.SOURCES["editor"][0], "commit": mods.SOURCES["editor"][1], "author": "pddmergilla",
             "license": "GPL-3.0", "note": "Each hack's new bytes only, made by harness/make_hack_patches.py"}
    OUT.write_text(json.dumps({"about": about, "hacks": out}, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} hacks, {OUT.stat().st_size} bytes")


if __name__ == "__main__":
    main()
