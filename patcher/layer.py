"""Co-op on top of another mod: a three-way merge of retail, the mod and co-op (design/M20, #144).

    python patcher/layer.py retail.bin mod.bin coop.bin out.bin

Every disc is track 1, raw 2352-byte sectors. A mod that patches retail files in place (the
randomizer, SOTN Editor's PPFs, most romhacks) and co-op touch different bytes. Co-op changes
36 instruction words in DRA.BIN and its last sector, and adds files after the last retail one.
Each sector is taken from whichever side changed it. A sector both changed is merged byte by
byte, and a byte both changed to different values is a conflict: the disc can't be layered.
The merged sectors' checksums are recomputed (sectors.py).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sectors  # noqa: E402


def files(image_path):
    """{path: (lba, size)} on an image file: scripts/check_disc_layout.py's (developer tools only;
    the app ships the patcher without scripts/)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from check_disc_layout import files as listing
    return listing(image_path)

SECTOR = sectors.SECTOR
CHECKED = 2072  # sync, header, subheader and a form 1 sector's 2048 data bytes: the rest are checksums
DATA = 24  # where a form 1 sector's data starts (after sync, header and subheader)


def merge(retail, mod, coop):
    """(merged image, report). report: sectors from each side, merged ones, and conflicts
    as (sector, byte offset in it)."""
    n = max(len(retail), len(mod), len(coop)) // SECTOR
    out = bytearray(n * SECTOR)
    report = {"mod": 0, "coop": 0, "merged": [], "conflicts": []}
    for i in range(n):
        at = i * SECTOR
        r, m, c = (bytes(x[at:at + SECTOR]) if len(x) >= at + SECTOR else None for x in (retail, mod, coop))
        if r is None:  # past the retail image: files a side added
            if m is not None and c is not None and m != c:
                report["conflicts"].append((i, 0))
            pick = c if c is not None else m
            out[at:at + SECTOR] = pick
            continue
        m = r if m is None else m
        c = r if c is None else c
        if c == r:
            out[at:at + SECTOR] = m
            report["mod"] += m != r
        elif m == r:
            out[at:at + SECTOR] = c
            report["coop"] += 1
        else:
            s = bytearray(r)
            for k in range(SECTOR):
                if c[k] == r[k]:
                    s[k] = m[k]
                elif m[k] == r[k] or m[k] == c[k]:
                    s[k] = c[k]
                elif k < CHECKED:
                    report["conflicts"].append((i, k))
            if sectors.is_data(s):
                sectors.seal(s)
            out[at:at + SECTOR] = s
            report["merged"].append(i)
    return out, report


def _conflict_runs(report):
    """Conflicting bytes as runs of whole instruction words: (sector, first byte, end byte)."""
    by_sector = {}
    for i, k in report["conflicts"]:
        if k >= DATA:
            by_sector.setdefault(i, set()).add(DATA + (k - DATA) // 4 * 4)
    runs = []
    for i, words in sorted(by_sector.items()):
        for w in sorted(words):
            if runs and runs[-1][0] == i and runs[-1][2] == w:
                runs[-1][2] = w + 4
            else:
                runs.append([i, w, w + 4])
    return runs


def relocate(out, retail, mod, coop, report):
    """Resolves the one kind of conflict a mod can't avoid: the mod put its own hook (a jal to a
    trampoline) on an instruction co-op also changed, and the trampoline runs the instructions it
    displaced. Then co-op's instructions go into the trampoline instead, and the mod's hook stays.
    The randomizer's FrameHook does this to the g_PlayableCharacter read co-op redirects.
    Changes out in place; moves what it resolved from report["conflicts"] to report["relocated"]."""
    report.setdefault("relocated", [])
    left = []
    for i, start, end in _conflict_runs(report):
        at = i * SECTOR
        was, ours = bytes(retail[at + start:at + end]), bytes(coop[at + start:at + end])
        # Words around the run that both sides also changed (bytes that happened to agree) belong to it.
        while start > DATA and retail[at + start - 4:at + start] != coop[at + start - 4:at + start] \
                and retail[at + start - 4:at + start] != mod[at + start - 4:at + start]:
            start -= 4
        while end < CHECKED and retail[at + end:at + end + 4] != coop[at + end:at + end + 4] \
                and retail[at + end:at + end + 4] != mod[at + end:at + end + 4]:
            end += 4
        was, ours = bytes(retail[at + start:at + end]), bytes(coop[at + start:at + end])
        found, j = [], mod.find(was)
        while j >= 0:
            s = j // SECTOR
            if s != i and retail[j:j + len(was)] != was and (j + len(was) - 1) // SECTOR == s:
                found.append(j)
            j = mod.find(was, j + 1)
        if len(found) != 1:
            left.extend((i, k) for i2, k in report["conflicts"] if i2 == i and start <= k < end)
            continue
        j = found[0]
        out[at + start:at + end] = mod[at + start:at + end]
        out[j:j + len(ours)] = ours
        for s in {i, j // SECTOR}:
            sec = out[s * SECTOR:(s + 1) * SECTOR]
            sectors.seal(sec)
            out[s * SECTOR:(s + 1) * SECTOR] = sec
        report["relocated"].append((i, start, j // SECTOR, j % SECTOR))
    report["conflicts"] = left


COLLECTIBLES = json.loads((Path(__file__).resolve().parent / "collectibles.json").read_text())


def _file(image, path):
    """A file's bytes from a raw image, and where each 2048-byte piece of it starts in the image."""
    from patcher import find_file
    lba, size = find_file(image, path)
    starts = [(lba + k) * SECTOR + DATA for k in range((size + 2047) // 2048)]
    return b"".join(image[a:a + 2048] for a in starts)[:size], starts


def collectibles(image):
    """What each placed collectible's castle flag gives on this disc: scripts/gen_collectibles.py's
    table, made from the disc's own PrizeDrops instead of the decomp's source. On retail it's the
    module's own table; on a randomized disc it follows the items the randomizer placed."""
    c = COLLECTIBLES
    table = [0] * c["n"]
    for st in c["stages"]:
        data, _ = _file(image, st["file"])
        for i in range(st["count"]):
            v = int.from_bytes(data[st["at"] + 2 * i:st["at"] + 2 * i + 2], "little")
            if v == c["life_vessel"]:
                code = 1
            elif v == c["heart_vessel"]:
                code = 2
            elif 0x80 <= v < 0x80 + 0x4000:
                v -= 0x80
                code = 0x8000 | v if v < c["hand_items"] else 0x4000 | (v - c["hand_items"])
            else:
                code = 0
            table[st["flag"] + i] = code
    return table


def adapt(image):
    """Fits co-op to the mod under it, in place: COOP.BIN's collectibles table is remade from the
    image's own stages. Returns how many entries changed."""
    data, starts = _file(image, "COOP.BIN")
    tag = COLLECTIBLES["magic"].encode()
    at = data.find(tag)
    if at < 0 or data.find(tag, at + 1) >= 0:
        raise ValueError("COOP.BIN's collectibles table isn't where it should be")
    n = int.from_bytes(data[at + 8:at + 12], "little")
    if n != COLLECTIBLES["n"]:
        raise ValueError(f"COOP.BIN's collectibles table has {n} entries, collectibles.json {COLLECTIBLES['n']}")
    new = b"".join(v.to_bytes(2, "little") for v in collectibles(image))
    old = data[at + 12:at + 12 + 2 * n]
    if new == old:
        return 0
    blob = bytearray(data)
    blob[at + 12:at + 12 + 2 * n] = new
    for k, a in enumerate(starts):
        piece = blob[k * 2048:(k + 1) * 2048]
        if image[a:a + len(piece)] != piece:
            image[a:a + len(piece)] = piece
            sec = a - DATA
            s = image[sec:sec + SECTOR]
            sectors.seal(s)
            image[sec:sec + SECTOR] = s
    return sum(1 for i in range(n) if new[2 * i:2 * i + 2] != old[2 * i:2 * i + 2])


def table_problems(retail, mod, coop, out):
    """Directory records the byte merge got wrong (paths of image files): each file must be where
    the side that moved or resized it put it. A record both sides changed is a conflict."""
    fr, fm, fc, fo = (files(Path(p)) for p in (retail, mod, coop, out))
    problems = []
    for path in set(fr) | set(fm) | set(fc) | set(fo):
        r, m, c = fr.get(path), fm.get(path), fc.get(path)
        if c != r and m != r and c != m:
            problems.append(f"{path}: changed by both")
            continue
        want = c if c != r else m
        if fo.get(path) != want:
            problems.append(f"{path}: {fo.get(path)}, not {want}")
    return problems


def where(image_path, sector):
    """The file a sector belongs to, on that image (or '' for the disc's own structures)."""
    for path, (lba, size) in files(Path(image_path)).items():
        if lba <= sector < lba + max(1, (size + 2047) // 2048):
            return path.split(";")[0]
    return ""


def main():
    retail, mod, coop, out = sys.argv[1:5]
    sides = [Path(p).read_bytes() for p in (retail, mod, coop)]
    image, report = merge(*sides)
    relocate(image, *sides, report)
    print(f"  {adapt(image)} collectibles follow the mod's items")
    for i, k, s, o in report["relocated"]:
        print(f"  relocated: co-op's hook at sector {i}+{k} ({where(retail, i)}) into the mod's trampoline at {s}+{o}")
    print(f"{report['mod']} sectors from the mod, {report['coop']} from co-op, {len(report['merged'])} merged")
    for i in report["merged"]:
        print(f"  merged: sector {i} ({where(retail, i)})")
    if report["conflicts"]:
        for i, k in report["conflicts"][:20]:
            print(f"  CONFLICT: sector {i} byte {k} ({where(retail, i)})")
        sys.exit(1)
    Path(out).write_bytes(image)
    problems = table_problems(retail, mod, coop, out)
    for p in problems:
        print(f"  DIRECTORY: {p}")
    if problems:
        Path(out).unlink()
        sys.exit(1)


if __name__ == "__main__":
    main()
