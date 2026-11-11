"""Stops a big job before it fills the disk (AGENTS.md, "Disk space").

    python scripts/disk_space.py [GB]    # exit 1, saying why, if less than GB (default 30) of room

Under WSL the Linux disk is a file on a Windows drive (C: unless moved). That file grows as Linux
writes and never shrinks, so Linux's own `df` shows plenty free while C: fills; when C: is full,
WSL stops dead (2026-11-06: 72 randomizer discs at 540 MB each). So under WSL the room is C:'s
free space plus what Linux has freed inside that file: a write reuses it before the file grows
(2026-11-11: 2 GB written with 44 GB freed inside, and the file stayed the same size). C: itself
never goes below FLOOR_GB, whatever the file holds.
"""

import glob
import os
import shutil
import sys
from pathlib import Path

NEEDED_GB = 30
FLOOR_GB = 20  # C:'s own free space, even with room inside the Linux disk


def where():
    wsl = Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists() or "microsoft" in Path("/proc/version").read_text().lower()
    return "/mnt/c" if wsl and Path("/mnt/c").exists() else "/"


def inside_gb():
    """Room Linux has freed inside its disk file on C: (0 if not under WSL, or the file isn't found)."""
    if where() == "/":
        return 0.0
    files = glob.glob("/mnt/c/Users/*/AppData/Local/wsl/*/ext4.vhdx") + \
        glob.glob("/mnt/c/Users/*/AppData/Local/Packages/*/LocalState/ext4.vhdx")
    if len(files) != 1:
        return 0.0  # none, or several distros: can't tell which is ours
    s = os.statvfs("/")  # blocks in use (disk_usage's free leaves out the root-reserved 5%)
    return max(0.0, (os.path.getsize(files[0]) - (s.f_blocks - s.f_bfree) * s.f_frsize) / 1e9)


def free_gb():
    return shutil.disk_usage(where()).free / 1e9


def check(needed_gb=NEEDED_GB):
    """Raises SystemExit, in words, if there's less than needed_gb of room before the disk that
    really fills is full, or C: itself is under FLOOR_GB. Returns the room in GB."""
    free, inside = free_gb(), inside_gb()
    room = free + inside
    if room < needed_gb or (inside and free < FLOOR_GB):
        raise SystemExit(f"Only {free:.0f} GB free on {where()} (+{inside:.0f} GB freed inside the Linux disk; needs "
                         f"{needed_gb}, and {FLOOR_GB} on {where()} itself): stopping before the disk fills. Delete "
                         f"built discs (.env/mods, .env/out) first, or keep big files on another drive.")
    return room


if __name__ == "__main__":
    room = check(float(sys.argv[1]) if len(sys.argv) > 1 else NEEDED_GB)
    print(f"{room:.0f} GB of room ({free_gb():.0f} free on {where()}, {inside_gb():.0f} freed inside the Linux disk)")
