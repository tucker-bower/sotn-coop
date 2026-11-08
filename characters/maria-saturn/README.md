# characters/maria-saturn

Saturn Maria: [SOTN Ultimate](https://github.com/renanbianchi/sotn-ultimate)'s Saturn Maria, a fork of Richter's code. Each player's launcher makes her from their own Saturn disc (docs/design/character-mods.md, D181).

| File | What it does |
|---|---|
| `coop_sat_maria.h` | Her partner build's link to co-op: its VRAM writes and palettes go to its own places. |
| `coop_sat_partner.c` | Her partner build's own copy of the palettes. |
| `make_patches.py` | Makes her patches. Her build ships with every array her art fills zeroed, and a manifest says where each goes. |
| `Makefile` | Builds her as player 1 (`SATMAR.BIN`) and as the partner (`SATMARP.BIN`), from upstream's `src/ric` plus `ultimate-ric.patch`. |
| `maria_saturn/` | SOTN Ultimate's four headers for her: attacks, Holy Beasts, double jump, her Richter changes (`df11991`). |
| `sat_maria.ld` | Linker script for her as player 1: data in Richter's slot, code at `0x80640000`. |
| `sat_maria_partner.ld` | Linker script for her as the partner, at `0x80200000`. |
| `ultimate-ric.patch` | SOTN Ultimate's changes to `src/ric` (`df11991`), against our pinned decomp. |

**Building her** takes the Saturn disc's files in `disks/saturn` and her generated headers. For now SOTN Ultimate's own generators make those headers on the dev machine (`GEN`, `ULT` in the Makefile; LOCAL.md). `launcher/saturn_maria.py` makes the same arrays byte for byte, and `make_patches.py` checks that they match.
