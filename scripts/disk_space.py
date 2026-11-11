"""Stops a big job before it fills the disk (AGENTS.md, "Disk space").

    python scripts/disk_space.py [GB]    # exit 1, saying why, if less than GB (default 30) is free

Under WSL the Linux disk is a file on a Windows drive (C: unless moved). That file grows as Linux
writes and never shrinks, so Linux's own `df` shows plenty free while C: fills; when C: is full,
WSL stops dead (2026-11-06: 72 randomizer discs at 540 MB each). So under WSL this checks C:.

With [paths] big_files set in env.toml (DEVELOPER_GUIDE.md, "Disk space"), the big files go to that
drive: it needs the GB, and the drive Linux's disk is on only FLOOR_GB, for code and test output.
"""

import shutil
import sys
from pathlib import Path

NEEDED_GB = 30
FLOOR_GB = 15  # the Linux disk's drive, when big files go elsewhere


def where():
    wsl = Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists() or "microsoft" in Path("/proc/version").read_text().lower()
    return "/mnt/c" if wsl and Path("/mnt/c").exists() else "/"


def big_files():
    """[paths] big_files, if set and there."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
    from coop_env import ENV
    p = ENV["paths"].get("big_files", "")
    return Path(p).expanduser() if p and Path(p).expanduser().is_dir() else None


def free_gb(at=None):
    return shutil.disk_usage(at or where()).free / 1e9


def check(needed_gb=NEEDED_GB):
    """Raises SystemExit, in words, if the disks that really fill have less than they need."""
    big, free = big_files(), free_gb()
    if big:
        room = free_gb(big)
        if room < needed_gb or free < FLOOR_GB:
            raise SystemExit(f"Only {room:.0f} GB free for big files in {big} (needs {needed_gb}), "
                             f"{free:.0f} GB on {where()} (needs {FLOOR_GB}): stopping before a disk fills.")
        return room
    if free < needed_gb:
        raise SystemExit(f"Only {free:.0f} GB free on {where()} (needs {needed_gb}): stopping before the disk "
                         f"fills. Delete built discs (.env/mods, .env/out) first, or set big_files (DEVELOPER_GUIDE.md).")
    return free


if __name__ == "__main__":
    big = big_files()
    room = check(float(sys.argv[1]) if len(sys.argv) > 1 else NEEDED_GB)
    print(f"{room:.0f} GB free for big files in {big}, {free_gb():.0f} on {where()}" if big
          else f"{room:.0f} GB free on {where()}")
