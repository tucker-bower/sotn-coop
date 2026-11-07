"""Layering co-op onto a modded disc (design/M20-randomizer.md): run after scripts/build_disc.sh.

    python patcher/test_layer.py

- On the plain co-op disc, the collectibles table made from the disc's own PrizeDrops is the
  module's built one, and adapting changes nothing.
- A mod that changed one of co-op's hook words (and has no trampoline to move it into) is a
  conflict, never a silently broken disc.
- Every randomizer disc harness/mods.py has built: its COOP.BIN gives what its own stages hold.
Nothing is written outside a temporary folder (game data: never commit it)."""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))
sys.path.insert(0, str(HERE.parent / "scripts"))
from check_disc_layout import bin_path  # noqa: E402
import layer  # noqa: E402
from patcher import find_file  # noqa: E402

FAILED = []


def check(ok, what, **about):
    print(("ok   " if ok else "FAIL ") + what + (f"  {about}" if about else ""))
    if not ok:
        FAILED.append(what)


def built_table(image):
    data, _ = layer._file(image, "COOP.BIN")
    at = data.find(layer.COLLECTIBLES["magic"].encode())
    n = layer.COLLECTIBLES["n"]
    return [int.from_bytes(data[at + 12 + 2 * i:at + 14 + 2 * i], "little") for i in range(n)]


def main():
    import mods
    from module import COOP_DISC
    retail = mods.RETAIL.read_bytes()
    coop = bin_path(COOP_DISC).read_bytes()

    image = bytearray(coop)
    check(layer.collectibles(image) == built_table(image), "plain co-op disc: the disc's table is the built one")
    check(layer.adapt(image) == 0 and image == coop, "plain co-op disc: adapting changes nothing")

    # A mod that rewrote one of co-op's hook words with something else: a conflict.
    lba, _ = find_file(retail, "DRA.BIN")
    def word_at(o):
        return (lba + o // 2048) * 2352 + 24 + o % 2048
    hook = next(o for o in range(0, 0x100000, 4) if retail[word_at(o):word_at(o) + 4] != coop[word_at(o):word_at(o) + 4])
    at = word_at(hook)
    mod = bytearray(retail)
    mod[at:at + 4] = b"\x00\x00\x00\x00"
    out, report = layer.merge(retail, mod, coop)
    layer.relocate(out, retail, mod, coop, report)
    check(bool(report["conflicts"]), "a mod that changed a hook word is a conflict", hook=hex(hook))

    names = [n for n in mods.MODS if n.startswith("rando-") and mods.disc(n)]
    for name in names:
        disc = bin_path(mods.disc(name)).read_bytes()
        info = mods.built(name)
        check(layer.collectibles(disc) == built_table(disc),
              f"{name}: COOP.BIN gives the randomizer's items", changed=info.get("collectibles_changed"))
    print(f"{len(names)} randomizer discs checked")
    if FAILED:
        sys.exit(1)


if __name__ == "__main__":
    main()
