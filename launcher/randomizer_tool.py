"""Rolls a randomized castle on the player's own PC (issue 232): the SOTN randomizer (sotnrando,
WTFPL), run by Node.js, both downloaded the first time and kept in the data folder's tools/.

    ready() -> True once both are there
    fetch(progress) -> downloads and checks them (raises OSError, in words)
    roll(preset, seed, out) -> the seed's .ppf (raises OSError)

Pinned and checked: Node by the SHA-256 nodejs.org publishes for that release; the randomizer at
the commit harness/mods.py tests (mods.SOURCES), by a hash of its files' contents (GitHub's zip
of a commit isn't promised to be the same bytes twice); its three packages by npm, against the
randomizer's own lockfile. On Windows it's always our Node; a developer's Linux uses its own.

Android can't run Node: there, a seed comes from sotn.io as a file.
"""

import hashlib
import io
import os
import random
import shutil
import string
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import paths

COMMIT = "3522dc67e3021d24c0e402f247c404c9d25ec56f"  # harness/mods.py SOURCES["randomizer"]: what the presets were tested at
RANDOMIZER = (f"https://codeload.github.com/sotnrando/sotnrando/zip/{COMMIT}",
              "c10c6bc0b8ed9fc5226c1063c161a8807afcb532fd1416aa96625d07c95ff055")
NODE_VERSION = "v22.23.4"
NODE = {"win32": (f"https://nodejs.org/dist/{NODE_VERSION}/node-{NODE_VERSION}-win-x64.zip",
                  "cbc74b5e0982c9dbb41525fd8fb5dcd32fbee237863f7829072f4639a1ce5f20")}
# The presets that work with co-op: all 72 but the four the randomizer's own command line can't make
# (harness/mods.py RANDO_CANT_MAKE); casual first, as the one to start with.
PRESETS = ["casual", "safe", "adventure", "og", "guarded-og", "sequence-breaker", "lycanthrope", "warlock", "nimble",
           "expedition", "bat-master", "scavenger", "empty-hand", "third-castle", "rat-race", "magic-mirror", "leg-day",
           "boss-rush", "aperture", "big-toss", "bounty-hunter", "target-confirmed", "hitman", "chaos-lite", "beyond",
           "breach", "grand-tour", "crash-course", "any-percent", "lookingglass", "skinwalker", "summoner", "agonize-twtw",
           "safe-stwo", "open", "brawler", "first-castle", "lucky-sevens", "sight-seer", "cursed-night", "spellbound",
           "mobility", "glitchmaster", "dog-life", "battle-mage", "timeline", "chimera", "vanilla", "oracle", "seeker",
           "all-bosses", "nimble-lite", "rampage", "cornivus", "max-rando", "mirror-breaker", "recycler", "anguish",
           "gear-rush", "rampage-aut25te", "lycanthrope-spr26te", "nimble-lite-spr26te", "warlock-spr26te",
           "april-fools", "gourmet-race", "collector", "hoarder"]
SURPRISE = "surprise"


def folder():
    return paths.data_dir() / "tools"


def _randomizer_dir():
    if os.environ.get("COOP_RANDOMIZER_DIR"):  # tests: a checkout already here (harness/mods.py's), no download
        return Path(os.environ["COOP_RANDOMIZER_DIR"])
    return folder() / f"sotnrando-{COMMIT[:12]}"


def _node():
    """The node to run: on Windows always ours (one another program put on the PATH could be any
    version); elsewhere (a developer's PC) the one installed."""
    if sys.platform == "win32":
        ours = folder() / f"node-{NODE_VERSION}-win-x64" / "node.exe"
        return ours if ours.exists() else None
    found = shutil.which("node")
    return Path(found) if found else None


def available():
    """Whether this PC can roll seeds at all (not on Android)."""
    from platform_android import ANDROID
    return not ANDROID and (sys.platform in NODE or shutil.which("node") is not None)  # (Windows downloads ours)


def ready():
    return bool(_node()) and (_randomizer_dir() / "node_modules" / "yargs").exists() and (_randomizer_dir() / "randomize").exists()


def _get(url, progress=None, opener=None):
    from report import VERSION
    req = urllib.request.Request(url, headers={"User-Agent": f"sotn-coop/{VERSION}"})
    data = bytearray()
    with (opener or urllib.request.urlopen)(req, timeout=60) as r:
        total = int(r.headers.get("Content-Length") or 0) if getattr(r, "headers", None) else 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            data += chunk
            if progress:
                progress(len(data), total or len(data) + 1)
    return bytes(data)


def tree_hash(z):
    """A zip's files by content, whatever the zip's own bytes."""
    h = hashlib.sha256()
    for name in sorted(n for n in z.namelist() if not n.endswith("/")):
        h.update(name.split("/", 1)[1].encode() + b"\0" + hashlib.sha256(z.read(name)).digest())
    return h.hexdigest()


def fetch(progress=None, opener=None):
    """Downloads and checks Node (unless there's one) and the randomizer, and installs its packages."""
    folder().mkdir(parents=True, exist_ok=True)
    try:
        if not _node():
            url, want = NODE[sys.platform]
            data = _get(url, progress, opener)
            if hashlib.sha256(data).hexdigest() != want:
                raise OSError("Node.js didn't download as published (its checksum differs)")
            zipfile.ZipFile(io.BytesIO(data)).extractall(folder())
        if not (_randomizer_dir() / "randomize").exists():
            z = zipfile.ZipFile(io.BytesIO(_get(RANDOMIZER[0], progress, opener)))
            if tree_hash(z) != RANDOMIZER[1]:
                raise OSError("the randomizer didn't download as tested (its files differ)")
            part = folder() / "randomizer.part"
            shutil.rmtree(part, ignore_errors=True)
            z.extractall(part)
            (part / z.namelist()[0].split("/")[0]).replace(_randomizer_dir())
            shutil.rmtree(part, ignore_errors=True)
        if not (_randomizer_dir() / "node_modules" / "yargs").exists():
            node = _node()
            npm = node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
            cmd = [str(node), str(npm)] if npm.exists() else ["npm"]
            r = subprocess.run(cmd + ["ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=_randomizer_dir(),
                               capture_output=True, text=True, timeout=600, **_quiet())
            if r.returncode:
                raise OSError("its packages didn't install: " + (r.stderr or r.stdout).strip().splitlines()[-1][:200])
    except OSError as e:
        raise OSError(f"Couldn't get the randomizer ({e}). Check your internet and try again, or use a seed file from sotn.io.") from e
    except Exception as e:  # noqa: BLE001
        raise OSError(f"Couldn't get the randomizer ({e}).") from e


def _quiet():
    """No console window flashing up on Windows."""
    return {"creationflags": 0x08000000} if sys.platform == "win32" else {}


def new_seed():
    return "".join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(10))


def roll(preset, seed, out):
    """The seed's .ppf, made by the randomizer. preset: one of PRESETS, or SURPRISE (a random one).
    seed: the player's, or "" for a random one. Returns (path, preset, seed). Raises OSError."""
    if preset == SURPRISE:
        preset = random.SystemRandom().choice(PRESETS)
    if preset not in PRESETS:
        raise OSError(f"{preset} isn't a preset that works with co-op")
    seed = (seed or "").strip() or new_seed()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(_node()), "randomize", "-p", preset, "-s", seed, "-q", "-o", str(out)], cwd=_randomizer_dir(),
                       capture_output=True, text=True, timeout=900, **_quiet())
    if r.returncode or not out.exists():
        raise OSError(f"The randomizer couldn't make that seed ({(r.stderr or r.stdout).strip()[-200:] or r.returncode}). Try another.")
    return out, preset, seed


def describe(preset):
    """A preset's description, from the randomizer once it's here: "" before."""
    import json
    try:
        return json.loads((_randomizer_dir() / "presets" / f"{preset}.json").read_text()).get("description", "")
    except (OSError, ValueError):
        return ""


os.environ.setdefault("NODE_NO_WARNINGS", "1")
