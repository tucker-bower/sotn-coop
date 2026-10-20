"""The co-op disc patcher (design/M6-playable-build.md, D71).

Players:
    python patcher.py apply <your SOTN .cue or .bin> [--patch sotn-coop.bps] [--out folder]
Makes the co-op disc next to yours (yours is never changed): "<name> (Co-op).cue", track 1
patched, track 2 (the CD audio) copied as it is.

Us, for a release:
    python patcher.py make <retail track 1 .bin> <co-op .bin from build_disc.sh> --out dist/

The patch holds only what differs from the retail disc (our code and the hook bytes, bps.py):
never game data.
"""

import argparse
import json
import re
import shutil
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bps  # noqa: E402

SECTOR = 2352
GAME_IDS = {                   # SYSTEM.CNF's boot file -> what to tell the player
    "SLUS_000.67": None,       # the right one
    "SLES_005.24": "This is the European (PAL) disc. Co-op needs the USA disc (SLUS-00067).",
    "SLES_005.25": "This is the European (PAL) disc. Co-op needs the USA disc (SLUS-00067).",
    "SLES_005.26": "This is the European (PAL) disc. Co-op needs the USA disc (SLUS-00067).",
    "SLES_005.27": "This is the European (PAL) disc. Co-op needs the USA disc (SLUS-00067).",
    "SLPM_860.23": "This is the Japanese disc. Co-op needs the USA disc (SLUS-00067).",
    "SLPS_910.11": "This is the Japanese reissue. Co-op needs the USA disc (SLUS-00067).",
}
DEFAULT_PATCH = Path(__file__).with_name("sotn-coop.bps")


class DiscError(Exception):
    """Something the player should be told, in plain words."""


def parse_cue(cue):
    """[(file, track mode)] in order."""
    tracks, current = [], None
    for line in Path(cue).read_text(errors="replace").splitlines():
        m = re.match(r'\s*FILE\s+"(.+)"\s+\w+', line) or re.match(r"\s*FILE\s+(\S+)\s+\w+", line)
        if m:
            current = Path(cue).parent / m[1]
        m = re.match(r"\s*TRACK\s+(\d+)\s+(\S+)", line)
        if m and current:
            tracks.append((current, m[2]))
    return tracks


def boot_file(track1):
    """The boot executable SYSTEM.CNF names (e.g. SLUS_000.67), or None. Reads the ISO 9660
    root directory from the raw MODE2/2352 image."""
    def sector(f, n):
        f.seek(n * SECTOR + 24)  # MODE2 form 1: 12 sync + 4 header + 8 subheader
        return f.read(2048)
    try:
        with open(track1, "rb") as f:
            pvd = sector(f, 16)
            if pvd[1:6] != b"CD001":
                return None
            root = int.from_bytes(pvd[156 + 2:156 + 6], "little")
            data = sector(f, root)
            i = 0
            while i < len(data) and data[i]:
                n = data[i]
                name = data[i + 33:i + 33 + data[i + 32]].decode("ascii", "replace")
                if name.upper().startswith("SYSTEM.CNF"):
                    cnf = sector(f, int.from_bytes(data[i + 2:i + 6], "little")).decode("ascii", "replace")
                    m = re.search(r"cdrom:\\?\\?([A-Z]{4}_\d{3}\.\d{2})", cnf, re.I)
                    return m[1].upper() if m else None
                i += n
    except OSError:
        return None
    return None


def find_track1(path):
    """(track 1 file, [other track files]) for a .cue or a single .bin."""
    path = Path(path)
    if not path.exists():
        raise DiscError(f"Can't find {path}.")
    if path.suffix.lower() == ".cue":
        tracks = parse_cue(path)
        if not tracks:
            raise DiscError("That .cue file doesn't list any tracks.")
        missing = [str(f.name) for f, _ in tracks if not f.exists()]
        if missing:
            raise DiscError(f"The .cue file points at {missing[0]}, which isn't next to it.")
        return tracks[0][0], [f for f, mode in tracks[1:] if f != tracks[0][0]]
    if path.suffix.lower() in (".chd", ".iso", ".img", ".pbp", ".ecm"):
        raise DiscError(f"{path.suffix} images aren't supported yet: use a .cue/.bin rip "
                        "(chdman can turn a .chd back into one: chdman extractcd).")
    return path, []


def check_disc(track1, patch):
    """Raises DiscError with what to do if track1 isn't the disc the patch is for."""
    src_size, _, _, crc_src, _ = bps.info(patch)
    game = boot_file(track1)
    if game and GAME_IDS.get(game, "x"):
        raise DiscError(GAME_IDS.get(game) or f"This disc is {game}, not Symphony of the Night (USA, SLUS-00067).")
    if game is None:
        raise DiscError("This doesn't look like a PlayStation disc image (no SYSTEM.CNF). Pick the .cue file of your rip.")
    size = track1.stat().st_size
    if size < src_size:
        raise DiscError("This rip of the USA disc is incomplete (too small). Rip it again.")
    crc = 0
    with open(track1, "rb") as f:
        left = src_size
        while left:
            chunk = f.read(min(left, 1 << 22))
            crc = zlib.crc32(chunk, crc)
            left -= len(chunk)
    if crc != crc_src:
        raise DiscError("This is the USA disc, but not an exact copy: it may be a damaged or modified rip. "
                        "A clean rip (one that matches redump.org) is needed.")
    return size > src_size  # a single .bin with the audio track after track 1


def apply(disc, patch_path=DEFAULT_PATCH, out_dir=None, progress=None):
    """Makes the co-op disc; returns the new .cue."""
    patch = Path(patch_path).read_bytes()
    track1, others = find_track1(disc)
    combined = check_disc(track1, patch)
    src_size, _, meta, _, _ = bps.info(patch)
    out_dir = Path(out_dir) if out_dir else track1.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(disc).stem.replace(" (Track 1)", "")
    out_bin = out_dir / f"{stem} (Co-op) (Track 1).bin"
    if combined:  # a single .bin with both tracks: patch from a copy of track 1
        tmp = out_dir / f"{stem} (Co-op) track1.tmp"
        with open(track1, "rb") as f, open(tmp, "wb") as t:
            left = src_size
            while left:
                chunk = f.read(min(left, 1 << 22))
                t.write(chunk)
                left -= len(chunk)
        bps.apply_file(tmp, patch, out_bin, progress)
        tmp.unlink()
    else:
        bps.apply_file(track1, patch, out_bin, progress)
    lines = [f'FILE "{out_bin.name}" BINARY', "  TRACK 01 MODE2/2352", "    INDEX 01 00:00:00"]
    audio = list(others)
    if combined:  # the audio track after track 1, inside the same file: copy it out
        audio_bin = out_dir / f"{stem} (Co-op) (Track 2).bin"
        with open(track1, "rb") as f, open(audio_bin, "wb") as t:
            f.seek(src_size)
            shutil.copyfileobj(f, t)
        audio = [audio_bin]
    for k, f in enumerate(audio, 2):
        if f.parent != out_dir or not f.name.startswith(stem + " (Co-op)"):
            target = out_dir / f"{stem} (Co-op) (Track {k}).bin"
            shutil.copyfile(f, target)
            f = target
        lines += [f'FILE "{f.name}" BINARY', f"  TRACK {k:02d} AUDIO", "    INDEX 00 00:00:00", "    INDEX 01 00:02:00"]
    cue = out_dir / f"{stem} (Co-op).cue"
    cue.write_text("\n".join(lines) + "\n")
    return cue


def make(retail_track1, coop_bin, out_dir, version):
    retail = Path(retail_track1).read_bytes()
    coop = Path(coop_bin).read_bytes()
    meta = json.dumps({"game": "SLUS-00067", "mod": "sotn-coop", "version": version}).encode()
    patch = bps.create(retail, coop, meta)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sotn-coop.bps").write_bytes(patch)
    info = bps.info(patch)
    (out / "manifest.json").write_text(json.dumps({
        "version": version, "game": "SLUS-00067", "source_size": info[0], "target_size": info[1],
        "source_crc32": f"{info[3]:08x}", "target_crc32": f"{info[4]:08x}", "patch_bytes": len(patch),
    }, indent=1))
    return out / "sotn-coop.bps"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply")
    a.add_argument("disc")
    a.add_argument("--patch", default=DEFAULT_PATCH)
    a.add_argument("--out")
    m = sub.add_parser("make")
    m.add_argument("retail_track1")
    m.add_argument("coop_bin")
    m.add_argument("--out", default="dist")
    m.add_argument("--version", default="dev")
    args = ap.parse_args()
    try:
        if args.cmd == "apply":
            print("made", apply(args.disc, args.patch, args.out))
        else:
            p = make(args.retail_track1, args.coop_bin, args.out, args.version)
            print("patch", p, p.stat().st_size, "bytes")
    except (DiscError, bps.PatchError) as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
