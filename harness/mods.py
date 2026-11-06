"""Other mods under co-op (design/M20, #144): each mod's disc, made from the retail disc on this
machine, with co-op layered on top (patcher/layer.py), and its savestates.

    python harness/mods.py [--boot] [name ...]   # build (every mod by default)
    python harness/mods.py --list

The mods come from their own repositories, checked out at pinned commits into .env/mods/src:
the randomizer (node), and SOTN Editor (its PPFs and its Extra Hacks, applied with the editor's
own code by editor_hacks.js). Everything built is game data: it stays in .env/mods.
--boot also makes each disc's savestates (savestates.py's route), which the mod_* tests need.
Each mod's build.json says how far it got: layered (with what was merged), booted, and whether the
entrance savestate fell back to the castle's first room (a mod that changed the entrance).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "patcher"))
sys.path.insert(0, str(HERE.parent / "scripts"))
import layer  # noqa: E402
import ppf  # noqa: E402
import sectors  # noqa: E402
from check_disc_layout import DATA, SECTOR, bin_path, files  # noqa: E402
from coop_env import DISKS, ENV_DIR, savestate  # noqa: E402

MODS_DIR = ENV_DIR / "mods"
RETAIL = DISKS / "Castlevania - Symphony of the Night (USA) (Track 1).bin"
TRACK2 = DISKS / "Castlevania - Symphony of the Night (USA) (Track 2).bin"
SOURCES = {
    "randomizer": ("https://github.com/sotnrando/sotnrando", "3522dc67e3021d24c0e402f247c404c9d25ec56f"),
    "editor": ("https://github.com/pddmergilla/sotn-editor", "7bf42de068e07068d439eebf29b9657b255e275f"),
}
SEED = "sotn-coop"

# The randomizer's presets, all of them (package.json). Each is one seed of that preset.
RANDO_PRESETS = [
    "casual", "safe", "adventure", "og", "guarded-og", "sequence-breaker", "lycanthrope", "warlock", "nimble",
    "expedition", "bat-master", "glitch", "scavenger", "empty-hand", "gem-farmer", "third-castle", "rat-race",
    "magic-mirror", "leg-day", "boss-rush", "aperture", "big-toss", "bounty-hunter", "target-confirmed", "hitman",
    "chaos-lite", "beyond", "breach", "grand-tour", "crash-course", "any-percent", "lookingglass", "skinwalker",
    "summoner", "agonize-twtw", "safe-stwo", "open", "brawler", "first-castle", "lucky-sevens", "bingo",
    "sight-seer", "cursed-night", "spellbound", "mobility", "glitchmaster", "dog-life", "battle-mage", "timeline",
    "chimera", "vanilla", "glitch-legacy", "oracle", "seeker", "all-bosses", "nimble-lite", "rampage", "cornivus",
    "max-rando", "mirror-breaker", "recycler", "anguish", "gear-rush", "rampage-aut25te", "lycanthrope-spr26te",
    "nimble-lite-spr26te", "warlock-spr26te", "april-fools", "gourmet-race", "collector", "hoarder",
]
# The randomizer's extras that patch code (its --help), all on at once, over the safe preset.
RANDO_EXTRAS = ["--turkey", "--colorrando", "--magicmax", "--antifreeze", "--mypurse", "--iws", "--fastwarp",
                "--noprologue", "--itemNameRandoMode"]
# SOTN Editor's Extra Hacks that it offers on a vanilla disc (its extra-hacks-catalog.js).
EDITOR_HACKS = [
    "minimap", "fast-warp", "damage-colors", "mist-gas-swap", "aggressive-enemy", "karasuman", "slogra",
    "dopplegangers", "succubus", "richter-no-flinch", "richter-ai", "richter-save", "quick-items", "mp-items",
    "heal-hearts", "instant-food", "eat-food-on-pickup", "subweapon-mp", "agunea-limit", "stopwatch-rework",
    "holy-water-richter", "wolf-no-jump", "subweapon-weapon", "heart-regen", "dark-stats", "dark-speed",
    "sky-walker", "faerie-behavior",
]

MODS = {f"rando-{p}": ("randomizer", ["-p", p]) for p in RANDO_PRESETS}
MODS["rando-extras"] = ("randomizer", ["-p", "safe", *RANDO_EXTRAS])
MODS["ass-final"] = ("ppf", "ass2/ASS-Final.ppf")
MODS.update({f"editor-{h}": ("hacks", [h]) for h in EDITOR_HACKS})
MODS["editor-all"] = ("hacks", EDITOR_HACKS)


def source(name):
    """The checkout of a mod's repository at its pinned commit."""
    url, rev = SOURCES[name]
    path = MODS_DIR / "src" / name
    if not (path / ".git").exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", url, str(path)], check=True)
    if subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() != rev:
        subprocess.run(["git", "-C", str(path), "fetch", "-q", "origin"], check=True)
        subprocess.run(["git", "-C", str(path), "checkout", "-q", rev], check=True)
    if name == "randomizer" and not (path / "node_modules").exists():
        subprocess.run(["npm", "install", "--silent"], cwd=path, check=True, capture_output=True)
    return path


def _stale(path):
    """Built before the current co-op disc: its COOP.BIN (and savestates) are an old module's."""
    from module import COOP_DISC
    return path.stat().st_mtime < bin_path(COOP_DISC).stat().st_mtime


def disc(name):
    """A mod's co-op disc (.cue), if it's been built on the current co-op disc."""
    cue = MODS_DIR / name / f"mod-{name}.cue"
    return cue if cue.exists() and not _stale(cue) else None


def built(name):
    p = MODS_DIR / name / "build.json"
    return json.loads(p.read_text()) if p.exists() and not _stale(p) else {}


def _write_files(image, changed):
    """Writes changed files (ISO path -> bytes, same size) into a raw image, sealing each sector."""
    table = {p.split(";")[0]: v for p, v in files(image).items()}
    data = bytearray(image.read_bytes())
    for path, blob in changed.items():
        lba, size = table[path]
        assert len(blob) == size, f"{path} changed size"
        for i in range((size + 2047) // 2048):
            at = (lba + i) * SECTOR
            chunk = blob[i * 2048:(i + 1) * 2048]
            data[at + DATA:at + DATA + len(chunk)] = chunk
            s = data[at:at + SECTOR]
            sectors.seal(s)
            data[at:at + SECTOR] = s
    image.write_bytes(data)


def mod_image(name, out):
    """Retail plus the mod (no co-op), written to out."""
    kind, arg = MODS[name]
    if kind == "randomizer":
        subprocess.run(["node", "randomize", "-i", str(RETAIL), "-o", str(out), "-s", SEED, "-q", *arg],
                       cwd=source("randomizer"), check=True, timeout=900)  # some seeds never settle
    elif kind == "ppf":
        out.write_bytes(ppf.apply(RETAIL.read_bytes(), (source("editor") / arg).read_bytes()))
    elif kind == "hacks":
        shutil.copyfile(RETAIL, out)
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp, "in"), Path(tmp, "out")
            table = {p.split(";")[0]: v for p, v in files(out).items()}
            raw = out.read_bytes()
            for path, (lba, size) in table.items():
                if path.endswith(".BIN") or path.startswith("SLUS"):
                    (src / path).parent.mkdir(parents=True, exist_ok=True)
                    (src / path).write_bytes(b"".join(raw[(lba + i) * SECTOR + DATA:(lba + i) * SECTOR + DATA + 2048]
                                                      for i in range((size + 2047) // 2048))[:size])
            r = subprocess.run(["node", str(HERE / "editor_hacks.js"), str(source("editor")), str(src), str(dst), ",".join(arg)],
                               capture_output=True, text=True)
            result = json.loads(r.stdout.strip().splitlines()[-1])
            if r.returncode:
                raise RuntimeError(result.get("error", r.stderr))
            _write_files(out, {p: (dst / p).read_bytes() for p in result["changed"]})


def build(name, boot=False):
    """Makes the mod's co-op disc (and with boot, its savestates). Returns its build.json."""
    from module import COOP_DISC
    d = MODS_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    info = {"mod": name}
    raw, out = d / "mod.bin", d / f"mod-{name}.bin"
    try:
        mod_image(name, raw)
        coop = bin_path(COOP_DISC)
        sides = [Path(p).read_bytes() for p in (RETAIL, raw, coop)]
        image, report = layer.merge(*sides)
        layer.relocate(image, *sides, report)
        info["collectibles_changed"] = layer.adapt(image)
        info["relocated"] = [f"{i}+{k} {layer.where(RETAIL, i)} -> {s}+{o} {layer.where(RETAIL, s)}"
                             for i, k, s, o in report["relocated"]]
        info["merged"] = [f"{i} {layer.where(RETAIL, i)}" for i in report["merged"]]
        info["conflicts"] = [f"{i}+{k} {layer.where(RETAIL, i)}" for i, k in report["conflicts"]]
        if report["conflicts"]:
            raise RuntimeError(f"{len(report['conflicts'])} bytes changed by both the mod and co-op")
        out.write_bytes(image)
        problems = layer.table_problems(RETAIL, raw, coop, out)
        if problems:
            out.unlink()
            raise RuntimeError(f"directory: {problems[:3]}")
        info["layered"] = True
        track2 = d / "track2.bin"
        if not track2.exists():
            track2.symlink_to(TRACK2)
        (d / f"mod-{name}.cue").write_text(f'FILE "{out.name}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
                                          'FILE "track2.bin" BINARY\n  TRACK 02 AUDIO\n    INDEX 00 00:00:00\n    INDEX 01 00:02:00\n')
        if boot:
            import savestates
            index = savestates.build(d / f"mod-{name}.cue")
            info["booted"] = True
            info["entrance_fallback"] = bool(index.get("entrance_fallback"))
    except Exception as exc:  # noqa: BLE001  (recorded: the compatibility table shows it)
        info["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        raw.unlink(missing_ok=True)
    (d / "build.json").write_text(json.dumps(info, indent=1))
    return info


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--list" in args:
        for n in MODS:
            b = built(n)
            print(f"{n:32} {'booted' if b.get('booted') else 'layered' if b.get('layered') else b.get('error', 'not built')}")
        sys.exit(0)
    boot = "--boot" in args
    names = [a for a in args if not a.startswith("--")] or list(MODS)
    for n in names:
        b = build(n, boot)
        print(n, "->", "booted" if b.get("booted") else "layered" if b.get("layered") else b.get("error"), flush=True)
