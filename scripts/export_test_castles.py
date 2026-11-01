#!/usr/bin/env python3
"""Exports the test castles (one outside each boss, one before each story scene: bossstarts.py)
from the harness's debug starts into launcher/assets/test-castles, which the installer and the
APK ship (Tucker, 2026-10-31: playtesters get them without making debug starts).

A test castle is a joint save: the game's memory card save (SaveData: the player's status,
settings, castle flags and map) of a player's progress, no game code or graphics, except its
memory card header (0x200 bytes), whose icon and palette are the game's. That header is blanked
here: the load doesn't read it (launcher/test_castles.py and harness test_castles_bundled check
every one loads and reaches its boss or scene).

Run after scripts/make_debug_starts.py when bossstarts.py's rows change."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STARTS = ROOT / ".env/fixtures/debug-starts"
OUT = ROOT / "launcher/assets/test-castles"
HEADER = 0x200  # SaveData.header (MemcardHeader: the card's title, icon and palette)


def main():
    index = json.loads((STARTS / "index.json").read_text())["starts"]
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.save"):
        old.unlink()
    rows, digest = {}, hashlib.sha256()
    for name, v in index.items():
        if not v.get("save"):
            continue
        blob = bytearray((STARTS / v["save"]).read_bytes())
        blob[:HEADER] = bytes(HEADER)
        (OUT / v["save"]).write_bytes(bytes(blob))
        rows[name] = {k: v[k] for k in ("about", "start", "order", "save")}
        digest.update(name.encode() + bytes(blob) + json.dumps(rows[name], sort_keys=True).encode())
    (OUT / "index.json").write_text(json.dumps({"id": digest.hexdigest()[:16], "castles": rows}, indent=1) + "\n")
    print(f"{len(rows)} test castles in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
