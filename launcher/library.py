"""The player's game discs (design/launcher-overhaul.md): the disc a castle is played on, with or
without mods. "Co-op (no mods)" is the co-op disc itself and always there; each other one is a
recipe of mods, kept small, and its image is built when it's used.

settings.json holds them:
    "game_discs": [{"id", "name", "mods": [...], "built": {"cue", "crc", "patch"}, "used"}]
    "game_disc": the id in use, or None for Co-op (no mods)
A mod in a recipe is one of:
    {"kind": "randomizer", "file": "<in this folder>.sdif" or "source": "<the player's file>", "info": seed_info}
    {"kind": "hacks", "ids": [...]}                       (patcher/mods/hacks.json)
    {"kind": "ass"}                                       (Alternate Scarlet Symphony -Final-, downloaded once)
    {"kind": "ppf", "file": "<in this folder>.ppf", "name": "<the file's name>", "crc": crc32}
Everything is in the data folder's game-discs/: the mods' files, and the images of the
KEEP_IMAGES discs used last (each is 540 MB: the others are made again when they're used).
"""

import hashlib
import json
import time
import uuid
import zlib
from pathlib import Path

import paths

KEEP_IMAGES = 3
ASS = {"name": "Alternate Scarlet Symphony -Final-", "file": "ASS-F.01.ppf",
       "url": "https://github.com/pddmergilla/sotn-editor/releases/download/ass-vF.01/ASS-F.01.ppf",
       "sha256": "004ccb8eadf14dcc4ba33bd511be5287adf3fba38b31b7b445f0c99b0d5ab259", "size": 5274564}
PLAIN = "Co-op (no mods)"


def folder():
    d = paths.data_dir() / "game-discs"
    (d / "mods").mkdir(parents=True, exist_ok=True)
    return d


def discs(settings):
    return [d for d in settings.get("game_discs") or [] if isinstance(d, dict) and d.get("id")]


def get(settings, did):
    return next((d for d in discs(settings) if d["id"] == did), None)


def current(settings):
    """The game disc in use, or None for Co-op (no mods)."""
    return get(settings, settings.get("game_disc"))


def hack_labels():
    import modded
    return {h: v["label"] for h, v in modded.hacks().items()}


def describe(disc):
    """A game disc in words, the same on every machine for the same mods (partners compare it):
    "Randomizer seed abc · casual (26.07.13) + Fast Warp, MiniMap". None: Co-op (no mods)."""
    if not disc:
        return None
    import randomizer
    labels = hack_labels()
    bits = []
    for m in disc.get("mods", []):
        if m["kind"] == "randomizer":
            bits.append("Randomizer " + randomizer.describe(m.get("info")))
        elif m["kind"] == "ass":
            bits.append(ASS["name"])
        elif m["kind"] == "ppf":
            bits.append(f"patch {m.get('crc', 0):08X}")
    hacks = sorted(labels.get(h, h) for m in disc.get("mods", []) if m["kind"] == "hacks" for h in m["ids"])
    if hacks:
        bits.append(("+ " if bits else "") + ", ".join(hacks))
    return " ".join(bits) if bits else PLAIN


def name(disc):
    """What the player calls it: the name they gave it, else what's in it."""
    return PLAIN if not disc else disc.get("name") or describe(disc)


def standing(disc):
    """How it stands with co-op, in a few words: "" (tested), "each part tested alone", or
    "untested with co-op"."""
    if not disc:
        return ""
    mods = disc.get("mods", [])
    if any(m["kind"] == "ppf" for m in mods):
        return "untested with co-op"
    parts = sum(1 for m in mods if m["kind"] in ("randomizer", "ass")) + (1 if any(m["kind"] == "hacks" for m in mods) else 0)
    return "each part tested alone" if parts > 1 else ""


def add(settings, mods, disc_name=None):
    """A new game disc (not built yet). Returns it."""
    disc = {"id": uuid.uuid4().hex[:10], "name": disc_name, "mods": mods, "built": None, "used": time.time()}
    settings["game_discs"] = discs(settings) + [disc]
    return disc


def remove(settings, did):
    disc = get(settings, did)
    if not disc:
        return
    _drop_image(disc)
    for m in disc.get("mods", []):
        if m.get("file") and not any(m.get("file") == o.get("file") for d in discs(settings) if d["id"] != did for o in d.get("mods", [])):
            (folder() / "mods" / m["file"]).unlink(missing_ok=True)
    settings["game_discs"] = [d for d in discs(settings) if d["id"] != did]
    if settings.get("game_disc") == did:
        settings["game_disc"] = None


def _drop_image(disc):
    d = folder() / disc["id"]
    if d.exists():
        for f in d.iterdir():
            f.unlink(missing_ok=True)
        d.rmdir()
    disc["built"] = None


def ready(disc, coop_patch):
    """Its image is built, for this version's co-op disc."""
    b = disc.get("built") or {}
    return bool(b.get("cue") and Path(b["cue"]).exists() and b.get("patch") == coop_patch)


# --- the mods' files

def keep_randomized(retail_track1, source):
    """A randomized disc (.cue / .bin) or a seed's .ppf, as a mod for a recipe: a .ppf is copied in,
    a disc is kept as the sectors that differ from retail (the player can delete theirs then).
    Raises DiscError, in words."""
    import patcher
    import ppf
    import randomizer
    import sectordiff
    source = Path(source)
    retail = Path(retail_track1).read_bytes()
    if source.suffix.lower() == ".ppf":
        data = source.read_bytes()
        try:
            image = ppf.apply(retail, data)
        except Exception as e:  # noqa: BLE001  (any malformed patch)
            raise patcher.DiscError(f"That .ppf file can't be read ({e}).") from e
        info = randomizer.seed_info(image, retail)
        if not info:
            raise patcher.DiscError("That .ppf isn't a randomizer seed (no seed on its title screen). "
                                    "For another mod, choose it under Another patch.")
        name = f"seed-{zlib.crc32(data):08x}.ppf"
        (folder() / "mods" / name).write_bytes(data)
        return {"kind": "randomizer", "file": name, "info": info}
    t1, _ = patcher.find_track1(source)
    if patcher.boot_file(t1) != "SLUS_000.67":
        raise patcher.DiscError("That isn't a randomized Symphony of the Night (USA) disc.")
    image = t1.read_bytes()[:len(retail)]
    if len(image) != len(retail):
        raise patcher.DiscError("That randomized disc isn't the same size as yours: it was made from another rip, "
                                "or it isn't a randomizer disc. Randomize your own disc on sotn.io and choose that.")
    info = randomizer.seed_info(image, retail)
    if not info:
        raise patcher.DiscError("That disc isn't randomized (it has no randomizer seed on its title screen).")
    diff = sectordiff.make(retail, image)
    name = f"seed-{zlib.crc32(diff):08x}.sdif"
    (folder() / "mods" / name).write_bytes(diff)
    return {"kind": "randomizer", "file": name, "info": info}


def keep_patch(retail_track1, source):
    """Any other .ppf, as a mod: copied in. Raises DiscError if it isn't one, or isn't for this disc."""
    import patcher
    import ppf
    data = Path(source).read_bytes()
    try:
        ppf.apply(Path(retail_track1).read_bytes(), data)
    except Exception as e:  # noqa: BLE001
        raise patcher.DiscError(f"That isn't a PPF patch for your disc ({e}).") from e
    crc = zlib.crc32(data)
    if hashlib.sha256(data).hexdigest() == ASS["sha256"]:
        return {"kind": "ass"}  # the tested one, dropped by hand: (it's copied where the download goes)
    name = f"patch-{crc:08x}.ppf"
    (folder() / "mods" / name).write_bytes(data)
    return {"kind": "ppf", "file": name, "name": Path(source).name, "crc": crc}


def ass_path():
    return folder() / "mods" / ASS["file"]


def have_ass():
    p = ass_path()
    return p.exists() and p.stat().st_size == ASS["size"]


def keep_ass_file(source):
    """Alternate Scarlet Symphony's .ppf, from a file the player has: copied in if it's the tested one."""
    data = Path(source).read_bytes()
    if hashlib.sha256(data).hexdigest() != ASS["sha256"]:
        return False
    ass_path().write_bytes(data)
    return True


def download_ass(progress=None, opener=None):
    """Downloads Alternate Scarlet Symphony -Final- (the release we tested) from its author's
    GitHub release, and checks it. Raises OSError, in words, if it can't."""
    import urllib.request
    if have_ass():
        return ass_path()
    url = __import__("os").environ.get("COOP_ASS_URL") or ASS["url"]  # tests: a local server
    req = urllib.request.Request(url, headers={"User-Agent": "sotn-coop"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=20) as r:
            data = bytearray()
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                data += chunk
                if progress:
                    progress(len(data), ASS["size"])
                if len(data) > ASS["size"] * 2:
                    break
    except Exception as e:  # noqa: BLE001
        raise OSError(f"Couldn't download it ({e}). Check your internet, or choose the .ppf if you have it.") from e
    if hashlib.sha256(bytes(data)).hexdigest() != ASS["sha256"]:
        raise OSError("The download wasn't the version we tested (its checksum differs), so it isn't used. Try again later.")
    part = ass_path().with_suffix(".part")
    part.write_bytes(bytes(data))
    part.replace(ass_path())
    return ass_path()


# --- building

def recipe(disc):
    """modded.make's mods for a disc. Raises DiscError if a file it needs is gone."""
    import patcher
    out = []
    labels = hack_labels()
    for m in disc.get("mods", []):
        if m["kind"] == "randomizer":
            p = folder() / "mods" / m["file"] if m.get("file") else Path(m.get("source") or "")
            if not p.exists():
                raise patcher.DiscError(f"The randomized disc this was made from is gone ({p.name}): make this game disc again.")
            what = "Randomizer " + __import__("randomizer").describe(m.get("info"))
            out.append({"name": what, "sectors": p.read_bytes()} if p.suffix.lower() == ".sdif" else
                       {"name": what, "ppf": p.read_bytes()} if p.suffix.lower() == ".ppf" else {"name": what, "disc": p})
        elif m["kind"] == "ass":
            if not have_ass():
                raise patcher.DiscError("Alternate Scarlet Symphony needs downloading again.")
            out.append({"name": ASS["name"], "ppf": ass_path().read_bytes()})
        elif m["kind"] == "ppf":
            p = folder() / "mods" / m["file"]
            if not p.exists():
                raise patcher.DiscError(f"{m.get('name', 'A patch')} is gone: make this game disc again.")
            out.append({"name": m.get("name") or "A patch", "ppf": p.read_bytes()})
        elif m["kind"] == "hacks" and m["ids"]:
            out.append({"name": ", ".join(labels.get(h, h) for h in m["ids"]), "hacks": list(m["ids"])})
    return out


def build(settings, disc, retail, coop_cue, coop_patch, progress=None):
    """Makes the disc's image (unless it's ready), keeping only the KEEP_IMAGES used last.
    Returns its .cue. Raises DiscError, in words."""
    import modded
    import patcher
    disc["used"] = time.time()
    if ready(disc, coop_patch):
        return Path(disc["built"]["cue"])
    mods = recipe(disc)
    for m in mods:
        if "disc" in m:  # an old randomizer setting, from the player's own randomized disc: kept as a diff now
            kept = keep_randomized(patcher.find_track1(retail)[0], m.pop("disc"))
            disc["mods"] = [kept if x["kind"] == "randomizer" else x for x in disc["mods"]]
            m["sectors"] = (folder() / "mods" / kept["file"]).read_bytes()
    others = sorted((d for d in discs(settings) if d["id"] != disc["id"] and (d.get("built") or {}).get("cue")),
                    key=lambda d: d.get("used", 0), reverse=True)
    for old in others[KEEP_IMAGES - 1:]:  # room for this one
        _drop_image(old)
    cue, crc, _ = modded.make(retail, coop_cue, mods, folder() / disc["id"], "Symphony of the Night (Co-op, modded)", progress)
    disc["built"] = {"cue": str(cue), "crc": crc, "patch": coop_patch}
    return cue


def migrate(settings):
    """The randomizer setting from before game discs ("randomizer": cue, source, info, crc, on):
    a game disc, in use if it was on. Its image is kept as it is until it needs making again."""
    r = settings.pop("randomizer", None)
    if not isinstance(r, dict) or not r.get("source") or discs(settings):
        return False
    src = Path(r["source"])
    mod = {"kind": "randomizer", "source": str(src), "info": r.get("info")}
    if src.suffix.lower() == ".ppf" and src.exists():
        name = f"seed-{zlib.crc32(src.read_bytes()):08x}.ppf"
        (folder() / "mods" / name).write_bytes(src.read_bytes())
        mod = {"kind": "randomizer", "file": name, "info": r.get("info")}
    disc = add(settings, [mod])
    if r.get("cue") and Path(r["cue"]).exists() and r.get("crc") is not None:
        disc["built"] = {"cue": r["cue"], "crc": r["crc"], "patch": r.get("patch")}
    if r.get("on"):
        settings["game_disc"] = disc["id"]
    return True


def to_json(disc):
    return json.dumps(disc, sort_keys=True)
