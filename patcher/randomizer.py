"""Co-op on a randomized disc (design/M20-randomizer.md): the player's disc, randomized by them
with the randomizer (sotn.io), with co-op layered on top.

    python patcher/randomizer.py <your SOTN .cue> <randomized .cue/.bin, or a .ppf> [--out folder]

Three discs meet on the player's machine: their own retail disc, the randomized one they made
from it (or a seed's .ppf, applied to the retail disc here), and the co-op disc the patcher made.
layer.py merges them, so nothing of the game or of the randomizer is shipped.
"""

import argparse
import shutil
import sys
import unicodedata
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import layer  # noqa: E402
import patcher  # noqa: E402
import ppf  # noqa: E402
from patcher import SECTOR, DiscError  # noqa: E402

# Where the randomizer writes the seed and "<version> <preset>" on the title screen (its
# util.js setSeedText): raw offsets in the track 1 image.
SEED_TEXT = (0x04389C6C, 30)
PRESET_TEXT = (0x04389C8C, 50)


def _text(image, at, length):
    raw = bytearray()
    for off in range(at, at + length):
        if off % SECTOR < 24 or off % SECTOR >= 24 + 2048:  # a sector's header or checksums
            continue
        raw.append(image[off])
    raw = bytes(raw).split(b"\0")[0]
    try:
        return unicodedata.normalize("NFKC", raw.decode("shift_jis")).replace("\u2212", "-").strip()
    except UnicodeDecodeError:
        return None


def seed_info(image, retail=None):
    """{"seed", "version", "preset"} that the randomizer wrote on this disc, or None if it isn't a
    randomized disc (retail's text there, or no text)."""
    seed = _text(image, *SEED_TEXT)
    about = _text(image, *PRESET_TEXT)
    if not seed or about is None:
        return None
    if retail is not None and _text(retail, *SEED_TEXT) == seed:
        return None
    version, _, preset = about.partition(" ")
    return {"seed": seed, "version": version, "preset": preset.strip()}


def describe(info):
    """In words, for the launcher: "seed abc · casual (26.07.13)"."""
    if not info:
        return "not randomized"
    return f"seed {info['seed']}" + (f" · {info['preset']}" if info.get("preset") else "") + \
        (f" ({info['version']})" if info.get("version") else "")


def _track1(path):
    track1, _ = patcher.find_track1(path)
    return track1


def make(retail_disc, mod, coop_cue, out_dir):
    """Makes "<name> (Co-op Randomizer).cue" in out_dir; returns (cue, seed_info, crc32 of track 1).
    Raises DiscError, in words for the player."""
    retail_t1 = _track1(retail_disc)
    retail = retail_t1.read_bytes()
    coop_t1 = _track1(coop_cue)
    coop = coop_t1.read_bytes()
    mod = Path(mod)
    if mod.suffix.lower() == ".ppf":
        try:
            randomized = ppf.apply(retail, mod.read_bytes())
        except Exception as e:  # noqa: BLE001  (any malformed patch)
            raise DiscError(f"That .ppf file can't be read ({e}).") from e
    else:
        t1 = _track1(mod)
        if patcher.boot_file(t1) != "SLUS_000.67":
            raise DiscError("That isn't a randomized Symphony of the Night (USA) disc.")
        randomized = t1.read_bytes()[:len(retail)]
    if len(randomized) != len(retail):
        raise DiscError("That randomized disc isn't the same size as yours: it was made from another rip, "
                        "or it isn't a randomizer disc. Randomize your own disc on sotn.io and choose that.")
    info = seed_info(randomized, retail)
    if not info:
        raise DiscError("That disc isn't randomized (it has no randomizer seed on its title screen).")
    image, report = layer.merge(retail, randomized, coop)
    layer.relocate(image, retail, randomized, coop, report)
    if report["conflicts"]:
        try:  # which file, with the developer tools (scripts/); the app says which sectors
            where = sorted({layer.where(retail_t1, i) or f"sector {i}" for i, _ in report["conflicts"][:20]})
        except ImportError:
            where = sorted({f"sector {i}" for i, _ in report["conflicts"][:20]})
        raise DiscError(f"Co-op can't be put on this randomizer seed: it changes the same code as co-op "
                        f"({', '.join(where)}). Try another preset, and tell us which one this was.")
    layer.adapt(image)
    del retail, coop, randomized
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(retail_disc).stem.replace(" (Track 1)", "")
    out_bin = out_dir / f"{stem} (Co-op Randomizer) (Track 1).bin"
    out_bin.write_bytes(image)
    crc = zlib.crc32(image)
    del image
    # The audio tracks: the co-op disc's (retail's, as they are), copied next to it.
    tracks = patcher.parse_cue(coop_cue) if str(coop_cue).lower().endswith(".cue") else []
    lines = [f'FILE "{out_bin.name}" BINARY', "  TRACK 01 MODE2/2352", "    INDEX 01 00:00:00"]
    for k, (f, mode) in enumerate(tracks[1:], 2):
        target = out_dir / f"{stem} (Co-op Randomizer) (Track {k}).bin"
        if Path(f).resolve() != target.resolve() and not (target.exists() and target.stat().st_size == Path(f).stat().st_size):
            shutil.copyfile(f, target)
        lines += [f'FILE "{target.name}" BINARY', f"  TRACK {k:02d} AUDIO", "    INDEX 00 00:00:00", "    INDEX 01 00:02:00"]
    cue = out_dir / f"{stem} (Co-op Randomizer).cue"
    cue.write_text("\n".join(lines) + "\n")
    return cue, info, crc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("retail")
    ap.add_argument("mod")
    ap.add_argument("coop", help="the co-op disc's .cue (patcher.py apply made it)")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()
    try:
        cue, info, crc = make(a.retail, a.mod, a.coop, a.out)
    except DiscError as e:
        print(e)
        sys.exit(1)
    print(f"made {cue}: {describe(info)}, crc {crc:08x}")


if __name__ == "__main__":
    main()
