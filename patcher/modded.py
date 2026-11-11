"""A game disc with mods under co-op (design/launcher-overhaul.md): the player's retail disc, any
number of mods on it, and co-op layered on top. Generalises randomizer.make, which takes one.

    make(retail_disc, coop_cue, mods, out_dir, stem) -> (cue, crc32 of track 1, report)

Each mod is a dict with "name" (in words, for messages) and one of:
- "sectors": a sector diff against retail (sectordiff.py: how a randomized disc is kept),
- "ppf": a PPF patch's bytes (a randomizer seed's, Alternate Scarlet Symphony, any other),
- "hacks": SOTN Editor's tested hacks, by id (patcher/mods/hacks.json: the bytes each writes).

The mods are applied to retail in that order. Two mods that change the same byte to different
values can't be on one disc; nor can a mod and co-op (layer.py). Either way DiscError says which,
in words for the player, and nothing is written.
"""

import json
import os
import shutil
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layer  # noqa: E402
import patcher  # noqa: E402
import ppf  # noqa: E402
import sectordiff  # noqa: E402
import sectors  # noqa: E402
from patcher import DiscError  # noqa: E402

SECTOR, DATA = sectors.SECTOR, 24
HACKS = Path(__file__).resolve().parent / "mods" / "hacks.json"


def _table():
    try:
        return json.loads(HACKS.read_text())
    except (OSError, ValueError):
        return {"hacks": [], "groups": []}


def hacks():
    """The tested hacks: {id: {"label", "summary", "files": {path: [[offset, hex], ...]}}}, or {}.
    A hack in a group (hacks that write shared code differently together) has its bytes there."""
    return {h["id"]: h for h in _table().get("hacks", [])}


def hack_writes(ids, table=None):
    """{path: [[offset, hex], ...]} the chosen hacks write: each one's own, and for each group,
    the patch for exactly the ones chosen from it."""
    table = table or _table()
    known = {h["id"]: h for h in table.get("hacks", [])}
    out = {}
    for hid in ids:
        if hid not in known:
            raise DiscError(f"There's no hack called {hid} in this version.")
        for path, runs in known[hid]["files"].items():
            out.setdefault(path, []).extend(runs)
    for g in table.get("groups", []):
        chosen = sorted(set(ids) & set(g["ids"]))
        if chosen:
            for path, runs in g["subsets"]["+".join(chosen)].items():
                out.setdefault(path, []).extend(runs)
    return out


def apply_hacks(image, ids, table=None, keep=False):
    """Writes the hacks' bytes into a raw image (a bytearray) in place, resealing each sector it
    touches. Returns {sector: what it was} (keep) or the sectors' numbers. Raises DiscError for a
    hack or a file that isn't there."""
    labels = {h["id"]: h["label"] for h in (table or _table()).get("hacks", [])}
    what = ", ".join(labels.get(i, i) for i in ids)
    touched = {}
    for path, runs in hack_writes(ids, table).items():
        place = patcher.find_file(image, path)
        if not place:
            raise DiscError(f"{what}: {path} isn't on this disc.")
        lba, size = place
        for offset, data in runs:
            data = bytes.fromhex(data)
            if offset + len(data) > size:
                raise DiscError(f"{what} doesn't fit this disc's {path}.")
            k = 0
            while k < len(data):  # across sectors: 2048 data bytes in each
                sector, at = lba + (offset + k) // 2048, (offset + k) % 2048
                n = min(len(data) - k, 2048 - at)
                start = sector * SECTOR + DATA + at
                if sector not in touched:
                    touched[sector] = bytes(image[sector * SECTOR:(sector + 1) * SECTOR]) if keep else None
                image[start:start + n] = data[k:k + n]
                k += n
    for i in touched:
        s = image[i * SECTOR:(i + 1) * SECTOR]
        sectors.seal(s)
        image[i * SECTOR:(i + 1) * SECTOR] = s
    return touched if keep else set(touched)


def _ppf_writes(image, patch):
    """[(offset, bytes)] a PPF writes, after checking it's for this image."""
    _, _, block, recs = ppf.records(patch)
    if block is not None and bytes(image[ppf.BLOCK_CHECK_AT:ppf.BLOCK_CHECK_AT + 1024]) != block:
        raise ppf.PpfError("this patch was made for a different disc image")
    return recs


def _diff_writes(diff):
    """[(offset, bytes)] a sector diff writes."""
    if diff[:4] != sectordiff.MAGIC:
        raise sectordiff.DiffError("not a sector diff")
    try:
        body = zlib.decompress(diff[12:])
    except zlib.error as e:
        raise sectordiff.DiffError(f"damaged ({e})") from e
    if len(body) % (4 + SECTOR):
        raise sectordiff.DiffError("damaged (cut short)")
    return [(int.from_bytes(body[at:at + 4], "little") * SECTOR, body[at + 4:at + 4 + SECTOR])
            for at in range(0, len(body), 4 + SECTOR)]


def mod_image(retail, mods, progress=None):
    """Retail with the mods on it, in order: (image, {sector: the mod that changed it}).
    Raises DiscError when two mods change one byte differently. Only the sectors a mod writes are
    copied to check that (a whole disc is 540 MB, and phones run this too)."""
    image = bytearray(retail)
    owner = {}
    for k, mod in enumerate(mods):
        name = mod.get("name", "A mod")
        try:
            if "hacks" in mod:
                writes = None
            elif "sectors" in mod:
                writes = _diff_writes(mod["sectors"])
            elif "ppf" in mod:
                writes = _ppf_writes(image, mod["ppf"])
            else:
                raise DiscError(f"{name} has nothing to apply.")
        except (ppf.PpfError, sectordiff.DiffError) as e:
            raise DiscError(f"{name} can't be applied: {e}") from e
        if writes is None:
            touched = apply_hacks(image, mod["hacks"], keep=True)
        else:
            touched = {}
            for offset, data in writes:
                if offset + len(data) > len(image):
                    image.extend(bytes(offset + len(data) - len(image)))
                for i in range(offset // SECTOR, (offset + len(data) - 1) // SECTOR + 1):
                    touched.setdefault(i, bytes(image[i * SECTOR:(i + 1) * SECTOR]))
                image[offset:offset + len(data)] = data
            for i in touched:
                s = image[i * SECTOR:(i + 1) * SECTOR]
                if len(s) == SECTOR and sectors.is_data(s) and "sectors" not in mod:  # a diff's sectors are whole already
                    sectors.seal(s)
                    image[i * SECTOR:(i + 1) * SECTOR] = s
        for i, mid in touched.items():
            now = image[i * SECTOR:(i + 1) * SECTOR]
            if now == mid:
                continue
            if i in owner:  # an earlier mod changed it too: the same bytes, differently?
                was = retail[i * SECTOR:(i + 1) * SECTOR]
                for b in range(DATA, DATA + 2048):
                    if mid[b] != was[b] and now[b] != mid[b]:
                        raise DiscError(f"{name} and {owner[i]} change the same part of the game, so they "
                                        "can't be on one disc. Leave one of them out.")
            owner.setdefault(i, name)
        if progress:
            progress(k + 1, len(mods) + 2)
    return image, owner


def make(retail_disc, coop_cue, mods, out_dir, stem, progress=None):
    """The game disc: "<stem>.cue" and its tracks in out_dir. Returns (cue, crc32, report)."""
    retail_t1, _ = patcher.find_track1(retail_disc)
    coop_t1, _ = patcher.find_track1(coop_cue)
    retail = retail_t1.read_bytes()
    modded, owner = mod_image(retail, mods, progress)
    coop = coop_t1.read_bytes()
    image, report = layer.merge(retail, modded, coop)
    layer.relocate(image, retail, modded, coop, report)
    if report["conflicts"]:
        names = sorted({owner.get(i, "a mod") for i, _ in report["conflicts"]})
        raise DiscError(f"Co-op can't be put on {', '.join(names)}: it changes the same code as co-op. "
                        "Leave it out, and tell us which it was.")
    layer.adapt(image)
    if progress:
        progress(len(mods) + 1, len(mods) + 2)
    del retail, coop, modded
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_bin = out_dir / f"{stem} (Track 1).bin"
    part = out_bin.with_suffix(".part")
    part.write_bytes(image)
    part.replace(out_bin)
    crc = zlib.crc32(image)
    del image
    # The audio tracks: the co-op disc's (retail's, as they are), linked or copied next to it
    lines = [f'FILE "{out_bin.name}" BINARY', "  TRACK 01 MODE2/2352", "    INDEX 01 00:00:00"]
    for k, (f, _mode) in enumerate(patcher.parse_cue(coop_cue)[1:], 2):
        target = out_dir / f"{stem} (Track {k}).bin"
        if not (target.exists() and target.stat().st_size == Path(f).stat().st_size):
            target.unlink(missing_ok=True)
            try:
                os.link(f, target)
            except OSError:
                shutil.copyfile(f, target)
        lines += [f'FILE "{target.name}" BINARY', f"  TRACK {k:02d} AUDIO", "    INDEX 00 00:00:00", "    INDEX 01 00:02:00"]
    cue = out_dir / f"{stem}.cue"
    cue.write_text("\n".join(lines) + "\n")
    if progress:
        progress(len(mods) + 2, len(mods) + 2)
    return cue, crc, report
