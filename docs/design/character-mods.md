# Richter and Maria from other mods

**Chosen (Tucker, 2026-11-07):** keep our characters, and add other mods' builds next to them. Ours become **Co-op Richter** and **Co-op Maria**: they use Alucard's gear, learn moves from relics and level up, each under a castle rule. **SOTN Ultimate**'s become **Ultimate Maria** and **Ultimate Richter**: they play as that mod built them. Giving players the choice is best. A mod character needs only what co-op itself needs, so they cost less to keep up than ours.

## What other mods have (read 2026-11-07)
| Mod | Characters | Form | Discs it needs |
|---|---|---|---|
| **SOTN Ultimate** ([renanbianchi/sotn-ultimate](https://github.com/renanbianchi/sotn-ultimate), AGPL, a sotn-decomp fork) | **PSP Maria** (`MARIA2.BIN`): upstream's `src/maria` plus its own glue (`mar2.c`), with her two sub-weapon slots, the PSP's Cat, Cardinal, Turtle, Dragon and Doll, PSP item drops and her PSP voice | C source on the decomp | the USA DXC (as ours) |
| | **Saturn Maria** (`src/ric` built again with `MOD_MARIA_SAT`) | C source | the Saturn disc |
| | **Saturn-coat Richter** (`RIC2.BIN`): retail Richter's code with the Saturn's coat sprites, and the JP flame-whip fix | C source plus generated art | the Saturn disc |
| SOTN Editor / ASS -Final- | Richter Mode, a Richter overhaul | a binary patch with no source; it runs only on an ASS image | ASS |

**Ultimate's Maria is ours, minus co-op, plus the PSP's sub-weapons.** Its `src/maria` matches our pinned decomp's except for one bug fix: she stuck when crouching after a landing (`pl_setstep.c`, under `MOD_SATURN`). Everything else is in `mar2.c`.

**Ultimate Richter is only a new coat.** Ultimate leaves Richter's moves alone. A Richter that plays differently would have to come from ASS's Richter Mode, and that's binary-only (see Options for Richter).

## How a mod character joins co-op
A mod character is its mod's sources, built as that mod builds them, with no `COOP_MARIA` or `COOP_RIC`. Our files sit next to them in `characters/<name>/`. The upstream change is one hunk, which turns on Ultimate's crouch fix (`MOD_SATURN`) in our build of her.

| Co-op needs | How |
|---|---|
| Her own character ID | `CHAR_ULT_MARIA 3` (`module/link.h`, `characters.py`, the lobby). She loads like Co-op Maria: a blob in expansion RAM, made on the player's PC from their DXC disc and our patches (D7, M8 §4). |
| The partner's body in the other game | Her partner build (`COOP_PARTNER` only, its own palettes, the same far trailer as Co-op Maria's) |
| The module drawing her as a puppet, and putting her art back after a load | `CoopMarBanks` and `CoopMarHooks` at the same fixed addresses as Co-op Maria's |
| Castle rules that make sense for any character | Damage taken and PvP apply. Levels, Alucard's stats, relic moves, extra jumps, off-hand weapons and familiars don't: those are Co-op characters' features. |

Ultimate's glue counts on three things in its own DRA. Our DRA hooks must stay the same size, so:
| Ultimate's DRA | Ours |
|---|---|
| `g_ModSubwpnIcons`, the HUD's sub-weapon icon table pointer | Her init copies her icons over DRA's table, as upstream's `mariapsp-forpsx` does |
| `g_ModMar2HudIcons`, which draws both her icons | The module calls her hook, at a fixed address, on the HUD's icon sprite each frame after DRA has drawn it |
| `MOD_STATUS_FLAGS` (`g_Status.saveName[11]`) | The same byte: co-op doesn't use it |

## Saturn Maria (Tucker, 2026-11-07: next, #185)
Ultimate's Saturn Maria is `src/ric` built again with `MOD_MARIA_SAT` (about 1,100 changed lines, and `mods/sotn-ultimate/src/maria_saturn/*.h`). Her art, palettes and animations are arrays compiled into her overlay, which Ultimate *generates* from the Saturn disc (`MARIA.PRG`, `MAR_W.CHR`, `STAGE_01.CHR`). Nothing a patch copies from one disc file could make them. Her sounds are made the same way.

| Option | What | Verdict |
|---|---|---|
| **A. Her overlay ships with those arrays blank; the launcher fills them** | As Ultimate's own browser builder does (its `ArraySpan`): our build records each generated array's offset, size and MD5, the patch carries zeros there, and a Python port of Ultimate's TypeScript converters (`tools/builder/src/mar_assets.ts` and what it imports, no numpy) fills them from the player's Saturn disc, checked against the MD5s. | ✅ Recommended. No game data ships; one converter per kind of art, tested against Ultimate's output. |
| B. Run Ultimate's own builder page | The player builds a full Ultimate disc in the browser, and we take her files from it | ❌ Every player needs all three discs and a browser step. |
| C. Bundle Node and run the TypeScript | | ❌ Big, and Android has no Node. |

**What Ultimate's DRA does for her, and ours instead** (our hooks stay size-neutral):
| Ultimate's DRA | Ours |
|---|---|
| Her Byakko and Seiryuu halt the game (`unk28` 4) and her code runs on (`5087C.c`) | The module runs her player update in that halt, as it runs the stage's for 0xFF (`character.c`) |
| Her walk snaps past x 0x7F-0x80 (`62DEC.c`) | The module snaps her, as `DoorWalkGround` does |
| Her sounds' priorities (`cd.c ModMarSfxPrio`) and her bank | Her blob's sound bank, as both Marias; her priority table set by her init |
| Her own Saturn HUD (`5F60C.c`, `F_GAME2` art) | Phase 2: Richter's HUD first |
| Alucard's Entrance music for her | Not done (cosmetic) |

**Phases.**
1. Spike, on the dev machine only: her overlay from Ultimate's generators, in Richter's slot, in co-op with Alucard. Proves the code runs on our DRA before any converter work.
2. Her blob made by the launcher: the array manifest, the Python converters for her art, Richter's HUD, Co-op Maria's voice where hers isn't made yet. `CHAR_SAT_MARIA`, the lobby, Settings › Game files › Saturn disc.
3. Her own sounds and Saturn HUD, from the disc.

**Acceptance criteria (Saturn Maria).**
1. She's chosen in the lobby once the player adds their Saturn disc (Redump, Track 1 MD5 `32f03757…`). The launcher makes her blob, and each generated array matches its MD5 (`launcher/test_characters.py`).
2. No Saturn data in the repo or the release: her patch's generated arrays are zeros (`release.py`'s check).
3. She plays as Ultimate built her: her attacks, specials, double jump and backdash (`saturn_maria_moves`), whatever the castle's rules.
4. Byakko and Seiryuu end their halt (`saturn_maria_beasts`).
5. She's the partner in Alucard's game and Alucard in hers (`partner_body_*_saturn_maria`), and she clears a boss with Alucard.

## Options for Richter
| Option | Verdict |
|---|---|
| **A. Ultimate Richter: retail moves in Co-op Richter's slot, with the Saturn coat** | ✅ Builds the same way as Ultimate Maria. It needs the Saturn disc. |
| B. ASS Richter Mode | ❌ Not now: binary-only, ASS images only, and it moves `RIC.BIN` on the disc. |

## Risks
- **The Saturn disc.** Ultimate Richter and Saturn Maria need it, and it isn't on the dev machine yet. Ultimate Maria comes first because she needs only the DXC disc.
- **PSP item drops.** Her Cat, Cardinal, Turtle and Dragon drop frames come from the PSP's DRA (`gen_mar2_items.py`), which our patch of `maria.bin` doesn't cover. Until the launcher also reads that file, drops show the PS1 art, and the pickups still work.
- **Two Marias in one session.** Each player's blob carries the character they play, and each game needs the other player's partner build. A Co-op Maria with an Ultimate Maria partner needs both builds, so the blob carries the other player's partner build when it differs.
- **Licence:** AGPL to AGPL, credited in `NOTICE`, the README and the file headers.

## Acceptance criteria
1. Ultimate Maria is chosen in the lobby and the launcher, apart from Co-op Maria. Her blob builds from the DXC disc, with no game data in the repo (`release.py`'s check).
2. Her glue differs from Ultimate's `mar2.c` only where the table above says (`diff` against the pinned Ultimate commit).
3. Her two slots: Circle swaps them, both icons show on the HUD, a Bible pickup gives the Doll and a dagger the Cat (`ultimate_maria_subweapons`).
4. She plays as Ultimate built her: no level-ups, no Alucard's-stats damage and no relic gates, whatever the castle's rules (`ultimate_maria_plays_as_ultimate`).
5. She's the partner in a game with Alucard and in one with Co-op Maria: her body follows, attacks and gets hurt (`partner_*_ultimate_maria`, the M13 checks).
6. She clears a boss with Alucard (`boss_*_alucard_and_ultimate_maria`).
7. Ultimate Richter meets criteria 1, 4 and 5, given the Saturn disc.
