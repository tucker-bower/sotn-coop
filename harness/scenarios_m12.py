"""M12 single-game tests (design/M12-coverage.md): playtest 2026-10-25 note 4, Maria's guardians."""

from link.mailbox import CHAR_MARIA
from module import COOP_DISC
from scenario import scenario
from scenarios_m8 import EQUIPMENT, LEATHER_SHIELD, mailbox, reload_as
from vram_survey import VRAM_W, vram

SHORT_SWORD = 19
# Maria's guardians in VRAM (src/maria/ovl_load.c, the PS1 layout): x, y in 16-bit words, 32x128
# each. A hand weapon's graphics load at x 0x240-0x27F, y 0x100-0x17F (right hand) and 0x180-0x1FF
# (left hand: src/dra/cd.c), over four of them.
GUARDIANS = {"owl": (0x240, 0x180), "cardinal": (0x260, 0x100), "dragon": (0x240, 0x100),
             "doll": (0x260, 0x180), "turtle": (0x2E0, 0x100), "cat": (0x2C0, 0x180)}


def block(v, x, y, w=0x20, h=0x80):
    return b"".join(v[2 * (row * VRAM_W + x):2 * (row * VRAM_W + x + w)] for row in range(y, y + h))


@scenario(start="entrance", disc=COOP_DISC)
def m12_maria_guardians_keep_their_graphics(run):
    """Playtest 2026-10-25 note 4: Maria's birds turned into a skull and a shield. A weapon or shield
    in her other hand must not overwrite her guardians' graphics."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_MARIA)
    run.step(60)
    before = vram(e)
    for item, what in ((SHORT_SWORD, "a short sword"), (LEATHER_SHIELD, "a shield")):
        e.write(EQUIPMENT, item)
        e.write(EQUIPMENT + 4, item)  # both hands: both weapon slots load
        reload_as(run, mb, CHAR_MARIA)
        run.step(120)
        after = vram(e)
        changed = [n for n, (x, y) in GUARDIANS.items() if block(before, x, y) != block(after, x, y)]
        run.expect(not changed, f"{what} in her hands: her guardians' graphics are intact", changed=changed)
