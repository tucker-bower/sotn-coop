# characters/maria-dx

Rebuilds Maria from the player's own *Dracula X Chronicles* disc and adds our co-op changes.

| File | What it does |
|---|---|
| `assets.pspus.maria.yaml` | Lists the assets to extract from the DXC disc. |
| `coop_maria.c` | Her co-op additions: power that grows like Alucard's, and the partner's start-up. |
| `coop_maria.h` | Her link to the co-op module, included in every file of the build. |
| `make_patches.py` | Makes the code-only patches that turn the player's DXC files into our Maria. |
| `Makefile` | Builds her as player 1 and as the partner. |
| `maria.ld` | Linker script for her as player 1. |
| `maria_partner.ld` | Linker script for her as the partner, in the 8 MB expansion RAM. |
| `splat.pspus.maria.yaml` | Splits her PSP binary into its code and data. |
