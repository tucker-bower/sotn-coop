"""Which disc a file is, by what's in it (design/launcher-overhaul.md): a file dropped on the
launcher goes to its own slot whichever slot it was dropped on. What each disc must be exactly
is checked afterwards, by what makes things from it (patcher.py, characters.py), in words for the
player.

    kind(path) -> "ps1", "psp", "saturn", or None (not a disc image we can tell)
"""

import re
from pathlib import Path

RAW_SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
SLOTS = ("ps1", "psp", "saturn")


def data_file(path):
    """The file with the disc's data: a .cue's first FILE (next to it), or the file itself."""
    path = Path(path)
    if path.suffix.lower() != ".cue":
        return path
    try:
        m = re.search(r'FILE\s+"([^"]+)"', path.read_text(errors="replace"))
    except OSError:
        return None
    return path.parent / m.group(1) if m else None


def kind(path):
    data = data_file(path)
    try:
        with open(data, "rb") as f:
            head = f.read(17 * 2352)
    except (OSError, TypeError):
        return None
    if b"SEGA SEGASATURN" in head[:64]:  # the Saturn's header, at the start of the data (after a raw sector's 16 bytes)
        return "saturn"
    if head[:12] == RAW_SYNC:  # raw 2352-byte sectors: a CD. The volume descriptor is sector 16
        volume = head[16 * 2352:17 * 2352]
        return "ps1" if b"PLAYSTATION" in volume else None
    if head[0x8001:0x8006] == b"CD001":  # 2048-byte sectors: an .iso
        if b"PSP GAME" in head[0x8008:0x8030]:
            return "psp"
        if b"PLAYSTATION" in head[0x8008:0x8030]:
            return "ps1"
    return None


def copy_in(path, folder, progress=None):
    """Copies a disc image (its .cue and every file it names, or a single file) into folder, and
    returns the copy's path. Already there: returned as it is."""
    import shutil
    path, folder = Path(path), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        if path.resolve().parent == folder.resolve():
            return path
    except OSError:
        pass
    files = [path]
    if path.suffix.lower() == ".cue":
        from patcher import cue_files  # (quoted names or not)
        files += [path.parent / n for n in cue_files(path.read_text(errors="replace"))]
    total = sum(f.stat().st_size for f in files if f.exists())
    done = 0
    for f in files:
        target = folder / f.name
        part = target.with_name(target.name + ".part")
        with open(f, "rb") as src, open(part, "wb") as dst:
            while True:
                chunk = src.read(1 << 22)
                if not chunk:
                    break
                dst.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        part.replace(target)
    return folder / path.name
