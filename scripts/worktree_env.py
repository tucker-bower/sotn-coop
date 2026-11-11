#!/usr/bin/env python3
"""A git worktree with a build environment of its own, and big files on a roomier drive.

    python3 scripts/worktree_env.py new <path> [--ref REF] [--rebuild]
    python3 scripts/worktree_env.py offload [--discs]

new: makes a worktree at <path> (detached at REF, default origin/main) with its own copy of this
checkout's environment in <path>/.env-local, so it can build and test a branch without touching
this one. Its decomp is reset to the worktree's patches/sotn-decomp.patch and builds the
worktree's code. --rebuild then runs scripts/rebuild_fixtures.sh there (about 15 minutes);
without it, run that yourself before the game tests. Copying takes about 4 GB.

offload: moves this environment's savestates, fixtures and mod discs (and, with --discs, the big
disc images in disks/) to [paths] big_files in env.toml, and links them back, so they no longer
grow the disk the code is on. On WSL that's a folder on another Windows drive, e.g. /mnt/e/sotn:
reading big files there is fast enough, but small files are slow, so code, toolchains and test
output stay on Linux's own disk. With big_files set, `new` puts the worktree's there from the start.

Both check scripts/disk_space.py first.
"""

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "scripts"))
import disk_space  # noqa: E402
from coop_env import DISKS, ENV, ENV_DIR  # noqa: E402

BIG = ("savestates", "fixtures", "mods")  # big files, each read or written whole
LEFT_OUT = ("out",) + BIG                 # not copied into a new worktree: its own builds and tests make them
BIG_DISC_MB = 100


def big_files():
    p = ENV["paths"].get("big_files", "")
    return Path(p).expanduser() if p else None


def run(*cmd, cwd=None):
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def move_and_link(src, dst):
    """Moves a file or folder to dst (another drive) and leaves a link at src. Copied and checked
    before the original goes."""
    if src.is_symlink():
        print(f"already linked: {src} -> {os.readlink(src)}")
        return
    if dst.exists():
        sys.exit(f"{dst} is already there: move it aside first")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, symlinks=True)
        diff = filecmp.dircmp(src, dst)
        if diff.left_only or diff.diff_files:
            sys.exit(f"copying {src} to {dst} didn't match: nothing removed")
        shutil.rmtree(src)
    else:
        shutil.copy2(src, dst)
        if not filecmp.cmp(src, dst, shallow=False):
            sys.exit(f"copying {src} to {dst} didn't match: nothing removed")
        src.unlink()
    src.symlink_to(dst)
    print(f"moved: {src} -> {dst}")


def offload(discs):
    big = big_files()
    if not big:
        sys.exit("Set [paths] big_files in env.toml first (DEVELOPER_GUIDE.md, \"Big files on another drive\")")
    env = ENV_DIR.resolve()
    for name in BIG:
        if (env / name).exists():
            move_and_link(env / name, big / env.parent.name / name)
    if discs:
        disks = DISKS.resolve()
        for f in sorted(disks.rglob("*")):
            if f.is_file() and not f.is_symlink() and f.stat().st_size > BIG_DISC_MB << 20:
                move_and_link(f, big / "disks" / f.relative_to(disks))


def new(target, ref, rebuild):
    target = Path(target).expanduser().resolve()
    src_env = ENV_DIR.resolve()
    decomp = src_env / "src" / "sotn-decomp"
    if not (decomp / ".git").exists():
        sys.exit(f"{src_env} has no decomp checkout: run scripts/bootstrap.sh here first")
    disk_space.check()
    if not target.exists():
        run("git", "fetch", "-q", "origin", cwd=ROOT)
        run("git", "worktree", "add", "--detach", target, ref, cwd=ROOT)
    env = target / ".env-local"
    if env.exists():
        sys.exit(f"{env} already exists")
    run("rsync", "-a", *[f"--exclude=/{d}" for d in LEFT_OUT], f"{src_env}/", f"{env}/")
    (env / "out").mkdir()
    big = big_files()
    for name in BIG:
        if big:
            where = big / target.name / name
            where.mkdir(parents=True, exist_ok=True)
            (env / name).symlink_to(where)
        else:
            (env / name).mkdir()
    (target / ".env").unlink(missing_ok=True)
    (target / ".env").symlink_to(".env-local")
    # the decomp builds this worktree's code, with this worktree's hooks
    wd = env / "src" / "sotn-decomp"
    coop = wd / "mods" / "co-op"
    if coop.is_symlink() or coop.exists():
        coop.unlink()
    coop.symlink_to(target)
    run("git", "checkout", "-q", "--", ".", ":!disks", cwd=wd)
    run("git", "apply", target / "patches" / "sotn-decomp.patch", cwd=wd)
    if not (target / "disks").exists():
        (target / "disks").symlink_to(DISKS.resolve())
    if (ROOT / "env.toml").exists() and not (target / "env.toml").exists():
        shutil.copy2(ROOT / "env.toml", target / "env.toml")
    print(f"\n{target} has its own environment.")
    if rebuild:
        run(target / "scripts" / "rebuild_fixtures.sh", cwd=target)
    else:
        print(f"Next: {target}/scripts/rebuild_fixtures.sh (about 15 minutes), then its tests.")
    print("When you switch its branch to one with another patches/sotn-decomp.patch, reset its decomp:\n"
          f"  cd {wd} && git checkout -- . ':!disks' && git apply {target}/patches/sotn-decomp.patch")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="a worktree with its own environment")
    n.add_argument("path")
    n.add_argument("--ref", default="origin/main")
    n.add_argument("--rebuild", action="store_true", help="then run scripts/rebuild_fixtures.sh there")
    o = sub.add_parser("offload", help="move big files to [paths] big_files and link them back")
    o.add_argument("--discs", action="store_true", help="the big disc images in disks/ too")
    args = ap.parse_args()
    if args.cmd == "new":
        new(args.path, args.ref, args.rebuild)
    else:
        offload(args.discs)


if __name__ == "__main__":
    main()
