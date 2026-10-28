#!/usr/bin/env python3
"""Builds the Windows installer and the Android app, and a DRAFT GitHub release of them
(design/M7b-polish.md part 1, design/M9-android.md).

    python3 scripts/release.py 0.7.1 [--notes docs/releases/v0.7.1.md] [--no-build] [--android] [--target BRANCH]

1. scripts/build_release.sh: the patch (from your disc and our build), the staged app, the
   installer (SOTN-Coop-setup-<version>.exe, in Emulators\\SOTN-Coop-release).
2. Checks that nothing in the installer's stage is game data: no disc images, savestates or
   memory cards anywhere, the only .bin is OpenBIOS, nothing is disc-sized, and every file of
   ours (app/) is of a kind on the allow-list.
3. gh release create v<version> --draft, with the installer uploaded as SOTN-Coop-setup.exe (a
   fixed name, so the README's .../releases/latest/download/SOTN-Coop-setup.exe always works),
   and SHA256SUMS.txt.
4. With --android (not yet: Tucker playtests it first): android/build.sh (it checks the app holds
   no game data), the APK uploaded as SOTN-Coop.apk (a fixed name too) and in SHA256SUMS.txt.
The release stays a draft: Tucker tests it and publishes it (D76). Publishing is one click on
GitHub, or: gh release edit v<version> --draft=false"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
REPO = "tucker-bower/sotn-coop"
ALLOWED = {".py", ".pyd", ".pyc", ".dll", ".exe", ".zip", ".txt", ".json", ".md", ".bps", ".map", ".toml",
           ".pth", ".cat", ".ttf", ".typed", ".pyi", ".cfg", ".ini", ".h", ".c", ".pxd", ".pyx", ".png", ".ico",
           ".tcl", ".jar", ".xml", ".so", ""}
MAX_FILE = 40 * 2 ** 20  # anything bigger than this would be a disc, not a program file


def sh(*cmd, **kw):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def emulators():
    sys.path.insert(0, str(MOD / "harness"))
    from coop_env import ENV, path
    return path(ENV["paths"]["win_emulators"])


def check_stage(stage):
    """Refuses anything that could be game data."""
    bad = []
    for f in stage.rglob("*"):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        ours = "app" in f.relative_to(stage).parts[:1]  # our files: strict; the Python runtime: no game data
        if ext == ".bin" and f.name != "openbios.bin":
            bad.append(f"{f}: a .bin that isn't OpenBIOS")
        elif ext in (".cue", ".iso", ".state", ".mcd", ".chd", ".img", ".ecm"):
            bad.append(f"{f}: a disc image, savestate or memory card")
        elif ours and ext not in ALLOWED and ext != ".bin":
            bad.append(f"{f}: not on the allow-list ({ext})")
        elif f.stat().st_size > MAX_FILE:
            bad.append(f"{f}: {f.stat().st_size} bytes")
    for name in ("README.txt", "AGPL-3.0.txt", "SwanStation-GPL-3.0.txt"):   # NOTICE, LICENSE, the core's GPL
        if not any(f.name == name and f.parent.name == "LICENSES" for f in stage.rglob(name)):
            bad.append(f"LICENSES/{name} missing: no release without the licences (NOTICE, LICENSE, licenses/)")
    if bad:
        raise SystemExit("game data check failed:\n  " + "\n  ".join(bad[:20]))
    n = sum(1 for f in stage.rglob("*") if f.is_file())
    print(f"game data check: {n} files, all program files")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version")
    ap.add_argument("--notes", help="release notes (markdown); default docs/releases/v<version>.md")
    ap.add_argument("--no-build", action="store_true", help="use the installer already built")
    ap.add_argument("--android", action="store_true", help="the Android app too")
    ap.add_argument("--target", default=None, help="the branch or commit the tag will point at")
    ap.add_argument("--published", action="store_true", help="allow replacing the installer of a published release")
    args = ap.parse_args()
    v = args.version
    out = emulators() / "SOTN-Coop-release"
    if not args.no_build:
        sh(MOD / "scripts" / "build_release.sh", v)
    check_stage(out / "stage")
    exe = out / f"SOTN-Coop-setup-{v}.exe"
    if not exe.exists():
        raise SystemExit(f"no installer: {exe}")
    notes = Path(args.notes) if args.notes else MOD / "docs" / "releases" / f"v{v}.md"
    if not notes.exists():
        raise SystemExit(f"no release notes: {notes}")
    tmp = Path(tempfile.mkdtemp(prefix="coop-release-"))
    fixed = tmp / "SOTN-Coop-setup.exe"
    shutil.copyfile(exe, fixed)
    assets = [fixed]
    if args.android:
        apk = MOD / ".env" / "android" / f"SOTN-Coop-{v}.apk"
        if not args.no_build:
            sh(MOD / "android" / "build.sh", v)
        if not apk.exists():
            raise SystemExit(f"no Android app: {apk} (android/build.sh {v})")
        assets.append(tmp / "SOTN-Coop.apk")
        shutil.copyfile(apk, assets[-1])
    sums = tmp / "SHA256SUMS.txt"
    sums.write_text("".join(f"{sha256(a)}  {a.name}\n" for a in assets))
    print(sums.read_text().strip())
    existing = subprocess.run(["gh", "release", "view", f"v{v}", "-R", REPO, "--json", "isDraft", "--jq", ".isDraft"],
                              capture_output=True, text=True)
    if existing.returncode == 0 and existing.stdout.strip() != "true" and not args.published:
        raise SystemExit(f"v{v} is published: refusing to replace what players download. "
                         "Use a new version, or --published if Tucker asked for it.")
    if existing.returncode == 0:
        sh("gh", "release", "upload", f"v{v}", *assets, sums, "--clobber", "-R", REPO)
        sh("gh", "release", "edit", f"v{v}", "--notes-file", notes, "-R", REPO)
    else:
        cmd = ["gh", "release", "create", f"v{v}", *assets, sums, "--draft", "--title", f"SOTN Co-op {v}",
               "--notes-file", notes, "-R", REPO]
        if args.target:
            cmd += ["--target", args.target]
        sh(*cmd)
    sh("gh", "release", "view", f"v{v}", "-R", REPO, "--json", "isDraft,url,assets",
       "--jq", '{draft: .isDraft, url: .url, assets: [.assets[].name]}')


if __name__ == "__main__":
    main()
