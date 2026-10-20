#!/usr/bin/env python3
"""Checks that this machine has everything SOTN Co-op needs, and says how to fix what's missing.

Run it first in every session: mods/co-op/scripts/doctor.py   (exit code 0 = all required checks pass)
Paths come from env.example.toml, overridden by env.toml.
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from coop_env import COOP, DISKS, ENV, REPO, TOOLS, path  # noqa: E402

BOOTSTRAP = "scripts/bootstrap.sh"
failures = 0


def check(ok, what, fix="", required=True):
    global failures
    mark = "✅" if ok else ("❌" if required else "⚠️ ")
    print(f"{mark} {what}" + ("" if ok or not fix else f"\n     fix: {fix}"))
    if not ok and required:
        failures += 1


def sha1(p):
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(*cmd):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)


print("== host tools")
for tool in ("mipsel-linux-gnu-gcc", "mipsel-linux-gnu-cpp", "mipsel-linux-gnu-ld", "go", "cargo", "ninja", "cmake", "7z", "gh"):
    check(shutil.which(tool), tool, f"{BOOTSTRAP} apt")
check((REPO / ".venv/bin/python").exists(), "python venv (.venv)", f"{BOOTSTRAP} python")
check((REPO / "tools/sotn_str/target/release/sotn_str").exists(), "decomp tool sotn_str", f"{BOOTSTRAP} decomp")

print("== emulator (harness)")
check(TOOLS["swanstation_core"].exists(), f"SwanStation core: {TOOLS['swanstation_core']}", f"{BOOTSTRAP} swanstation")
check((TOOLS["bios_dir"] / "scph5501.bin").exists(), "OpenBIOS (as scph5501.bin)", f"{BOOTSTRAP} openbios")

print("== discs")
for name, disc in ENV["discs"].items():
    rel = disc.get("cue") or disc["iso"]
    image = (DISKS / rel) if "/" not in rel and "\\" not in rel else path(rel)
    req = disc.get("required", False)
    if not image.exists():
        check(False, f"{name}: {image.name} missing", f"put it in {image.parent} (masters: {ENV['paths']['win_masters']})", req)
        continue
    for fname, want in disc.get("sha1", {}).items():
        check(sha1(image.parent / fname) == want, f"{name}: {fname} sha1", "not the verified dump; re-copy from masters", req)
    if "sha1" not in disc:
        check(True, f"{name}: {image.name} present (no known-good hash yet)")

print("== matching build")
r = run("sha1sum", "--quiet", "-c", "config/check.us.sha")
bad = [l for l in r.stdout.splitlines() if l]
check(r.returncode == 0, "us build matches retail (115 files)" if r.returncode == 0 else f"us build: {len(bad)} files differ or missing",
      f"{BOOTSTRAP} decomp   (if a first build failed, rm -rf build/us first)")

print("== Windows side")
for key in ("win_emulators", "win_masters"):
    check(path(ENV["paths"][key]).exists(), f"{key}: {ENV['paths'][key]}", "edit env.toml", required=False)

print("== hygiene")
tracked = subprocess.run(["git", "ls-files", "disks", "*.iso", "*.cue", "*.bin", "*.state", "*.mcd", ".env"],
                         cwd=COOP, capture_output=True, text=True).stdout.split()
tracked = [t for t in tracked if not t.endswith("README")]
check(not tracked, "no game data tracked by git", f"git rm --cached {' '.join(tracked)}")
check(run("gh", "auth", "status").returncode == 0 if shutil.which("gh") else False,
      "gh logged in (needed for PRs)", "gh auth login", required=False)

print(f"\n{'all required checks pass' if not failures else f'{failures} required check(s) failed'}")
sys.exit(1 if failures else 0)
