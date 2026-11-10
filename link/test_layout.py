"""The mailbox's layout, said twice: module/link.h for the game, link/mailbox.py for the host.

    python link/test_layout.py

The host reads and writes the game's memory by offset, so the two must agree to the byte: a
field that moves in one and not the other writes the partner over something else, and nothing
says so. The module's build checks link.h's offset comments against the compiler's
(module/coop.c's asserts); this checks mailbox.py against those comments, and every constant the
two files both name."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from link import mailbox as mb  # noqa: E402
from link import transport  # noqa: E402

# mailbox.py's name for a CoopLink field's offset
FIELDS = {
    "SELF": "self", "PARTNER": "partner", "PARTNER_AGE": "partnerAge", "OUT_RING": "out", "IN_RING": "in",
    "DROPPED": "dropped", "CMD": "cmd", "CMD_DONE": "cmdDone", "SAVE_SEQ": "saveSeq", "SAVE_OUT": "saveOut",
    "SAVE_IN": "saveIn", "SAVE_BLOCK": "saveBlock", "CARD_RESULT": "cardResult", "RANK": "rank",
    "SNAP_OUT_SEQ": "snapOutSeq", "SNAP_OUT": "snapOut", "SNAP_IN_SEQ": "snapInSeq", "SNAP_IN": "snapIn",
    "CONTROL": "control", "CHARACTER": "character", "OPTIONS": "options", "PAD_EXTRA": "padExtra",
    "SELF_SPRITES": "selfSpriteCount", "PARTNER_SPRITES": "partnerSpriteCount", "SELF_PRIMS": "selfPrimCount",
    "PARTNER_PRIMS": "partnerPrimCount", "SELF_PAD": "selfPad", "PARTNER_PAD": "partnerPad",
    "SELF_HITS": "selfHitCount", "PARTNER_HITS": "partnerHitCount", "RULES": "rulesOff",
}
# link.h's name -> mailbox.py's, where they differ (the rest are compared under the same name)
ALIASES = {
    "COOP_LINK_VERSION": "LINK_VERSION", "COOP_RING_SIZE": "RING_SIZE", "COOP_SPRITES": "N_SPRITES",
    "COOP_PRIMS": "N_PRIMS", "COOP_PRIM_SIZE": "PRIM_SIZE", "COOP_HITS": "N_HITS",
    "WEAPON_SELF_ADDR": "WEAPON_SELF", "WEAPON_PARTNER_ADDR": "WEAPON_PARTNER",
    "FAMILIAR_SELF_ADDR": "FAMILIAR_SELF", "FAMILIAR_PARTNER_ADDR": "FAMILIAR_PARTNER",
    "STATUS_PARTNER_ADDR": "STATUS_PARTNER",
    **{f"PRESENCE_{n}": n for n in ("IN_PLAY", "SPRITE", "PAUSED", "BUSY", "DEAD", "BOSS", "CUTSCENE", "CS_FOLLOWER")},
}
# sizes link.h gives in a struct's closing comment -> what the host uses for it
SIZES = {
    "CoopPresence": mb.Presence.SIZE, "CoopEvent": mb.EVENT_SIZE, "CoopCommand": mb._COMMAND.size,
    "CoopSprite": mb.SPRITE_SIZE, "CoopHit": mb.HIT_SIZE, "CoopWeapon": mb.WEAPON_SIZE,
    "CoopFamiliar": mb.FAMILIAR_SIZE, "CoopStatus": 4 + sum(n for _, n in mb.STATUS_RANGES),
    "CoopRing": 8 + mb.RING_SIZE * mb.EVENT_SIZE,
}


def main():
    failures = []

    def check(ok, what):
        if not ok:
            print("FAIL " + what)
            failures.append(what)

    h = (ROOT / "module" / "link.h").read_text()
    api = (ROOT / "module" / "coop_api.h").read_text()
    link = h[h.index("u32 magic; // COOP_MAGIC"):h.index("} CoopLink;")]
    offsets = {name: int(off, 16) for off, name in re.findall(r"/\* (0x[0-9A-Fa-f]+) \*/ \w+ (\w+)", link)}
    for py, field in FIELDS.items():
        check(field in offsets and getattr(mb, py) == offsets[field],
              f"mailbox.{py} is {getattr(mb, py):#x}, link.h's {field} is at {offsets.get(field, -1):#x}")
    print(f"ok   {len(FIELDS)} mailbox offsets match link.h's")

    defines = {n: int(v, 0) for n, v in re.findall(r"^#define (\w+) (0x[0-9A-Fa-f]+|\d+)\b", h + api, re.M)}
    compared = 0
    for name, value in defines.items():
        py = ALIASES.get(name, name)
        if hasattr(mb, py) and isinstance(getattr(mb, py), int):
            compared += 1
            check(getattr(mb, py) == value, f"mailbox.{py} is {getattr(mb, py):#x}, link.h's {name} is {value:#x}")
    check(compared >= 80, f"only {compared} constants were found in both files: has one of them been renamed?")
    print(f"ok   {compared} constants the two files both name are equal")

    sizes = {n: int(v, 0) for n, v in re.findall(r"^\} (\w+); // size = (0x[0-9A-Fa-f]+|\d+)", h, re.M)}
    for name, size in SIZES.items():
        check(sizes.get(name) == size, f"link.h's {name} is {sizes.get(name, 0):#x} bytes, the host's is {size:#x}")
    check((mb.STATUS_RANGES[0], mb.STATUS_RANGES[1]) == ((defines["STATUS_A"], defines["STATUS_A_SIZE"]),
                                                         (defines["STATUS_B"], defines["STATUS_B_SIZE"])),
          "mailbox.STATUS_RANGES aren't link.h's STATUS_A and STATUS_B")
    check(transport.PRESENCE_SIZE == mb.Presence.SIZE, "transport.PRESENCE_SIZE isn't the presence's size")
    check(transport.MAX_SNAP_RAW == mb.SNAP_MAX == defines["SNAP_MAX"], "SNAP_MAX differs between link.h, mailbox.py and transport.py")
    check(mb._RULES.size == offsets["rulesPad"] + 2 - offsets["rulesOff"], "mailbox._RULES isn't the size of link.h's rules")
    check(mb._HEADER.size == offsets["self"], "mailbox._HEADER isn't what comes before the presence")
    print(f"ok   {len(SIZES)} record sizes match")

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
