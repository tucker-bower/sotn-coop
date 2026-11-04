"""Co-op on top of another mod: a three-way merge of retail, the mod and co-op (design/M20, #144).

    python patcher/layer.py retail.bin mod.bin coop.bin out.bin

Every disc is track 1, raw 2352-byte sectors. A mod that patches retail files in place (the
randomizer, SOTN Editor's PPFs, most romhacks) and co-op touch different bytes. Co-op changes
36 instruction words in DRA.BIN and its last sector, and adds files after the last retail one.
Each sector is taken from whichever side changed it. A sector both changed is merged byte by
byte, and a byte both changed to different values is a conflict: the disc can't be layered.
The merged sectors' checksums are recomputed (sectors.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sectors  # noqa: E402
from check_disc_layout import files  # noqa: E402

SECTOR = sectors.SECTOR
CHECKED = 2072  # sync, header, subheader and a form 1 sector's 2048 data bytes: the rest are checksums


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
    image, report = merge(*(Path(p).read_bytes() for p in (retail, mod, coop)))
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
