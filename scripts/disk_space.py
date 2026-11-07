"""Stops a big job before it fills the disk (AGENTS.md, "Disk space").

    python scripts/disk_space.py [GB]    # exit 1, saying why, if less than GB (default 30) is free

Under WSL the Linux disk is a file on a Windows drive (C: unless moved). That file grows as Linux
writes and never shrinks, so Linux's own `df` shows plenty free while C: fills; when C: is full,
WSL stops dead (2026-11-06: 72 randomizer discs at 540 MB each). So under WSL this checks C:.
"""

import shutil
import sys
from pathlib import Path

NEEDED_GB = 30


def where():
    wsl = Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists() or "microsoft" in Path("/proc/version").read_text().lower()
    return "/mnt/c" if wsl and Path("/mnt/c").exists() else "/"


def free_gb():
    return shutil.disk_usage(where()).free / 1e9


def check(needed_gb=NEEDED_GB):
    """Raises SystemExit, in words, if the disk that really fills has less than needed_gb free."""
    free = free_gb()
    if free < needed_gb:
        raise SystemExit(f"Only {free:.0f} GB free on {where()} (needs {needed_gb}): stopping before the disk "
                         f"fills. Delete built discs (.env/mods, .env/out) first.")
    return free


if __name__ == "__main__":
    print(f"{check(float(sys.argv[1]) if len(sys.argv) > 1 else NEEDED_GB):.0f} GB free on {where()}")
