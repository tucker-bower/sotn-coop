# characters/richter-ps1

Rebuilds the game's Richter with our co-op changes, for the co-op disc.

| File | What it does |
|---|---|
| `coop_partner.c` | Redirects the partner's VRAM reads and writes to the second bank; Maria's build uses it too. |
| `coop_player.ld` | Fixed addresses of the module data both characters read. |
| `coop_ric.c` | His co-op additions: power that grows like Alucard's, and his frame tables. |
| `coop_ric.h` | His link to the co-op module, included in every file of the build. |
| `Makefile` | Builds him as player 1 and as the partner. |
| `ric.ld` | Linker script for him as player 1. |
| `ric_partner.ld` | Linker script for him as the partner, in the 8 MB expansion RAM. |
