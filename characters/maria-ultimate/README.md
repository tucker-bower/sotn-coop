# characters/maria-ultimate

Ultimate Maria: [SOTN Ultimate](https://github.com/renanbianchi/sotn-ultimate)'s PSP Maria, built from the player's own *Dracula X Chronicles* disc, as that mod plays her (docs/design/character-mods.md).

| File | What it does |
|---|---|
| `coop_ult_maria.h` | Her link to co-op, included in every file of her build: Ultimate's flags byte, and the partner build's VRAM and palettes. |
| `Makefile` | Builds her as player 1 (`ULTMAR.BIN`) and as the partner (`ULTMARP.BIN`), from upstream's `src/maria` without Co-op Maria's changes. `characters/maria-dx/make_patches.py` makes her patches. |
| `mar2.c` | SOTN Ultimate's glue (its `src/maria_psp/mar2.c` at `df11991`), with each co-op change marked `co-op:`. |
| `ult_maria.ld` | Linker script for her as player 1: Co-op Maria's layout, plus her HUD hook at `0x8013C7F8`. |
| `ult_maria_partner.ld` | Linker script for her as the partner, in the 8 MB expansion RAM. |
