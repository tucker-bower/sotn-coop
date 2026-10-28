# M16 design: Saturn characters

**Status:** approved by Tucker (2026-10-27).

## Goal
Three more choices in the lobby, each from the player's own discs, all optional:
- **Saturn Maria** and **the long-coat Richter**, from the Japanese Saturn release (T-9527G);
- **the Saturn character select screen**, used for the lobby pick when a Saturn disc is there;
- **Alucard with the 2007 recast voice**, from the PSP *Dracula X Chronicles* (USA or Europe).

Nothing new is needed by anyone who doesn't have these discs: they're added on the game-files screen, like PSP Maria.

## Where the code comes from
| Option | Idea | Verdict |
|---|---|---|
| **A. Build on the other project's overlays (recommended)** | Their `decomp-mods/mariasat-forpsx` and `richter2-forpsx` are PS1 player overlays in C, built on sotn-decomp, under AGPL-3.0 like ours. We vendor them (credited, with their history noted), adapt them to our module's character interface (M8) and the M13 partner swap | ✅ Weeks of reverse engineering already done. AGPL to AGPL is allowed with credit and source. |
| B. Our own ports from the decomp | Port Saturn Maria and Richter's Saturn code ourselves | ❌ Weeks, for the same result |

## How the player gets them (no Docker, no compiler)
Our PSP Maria already works this way (`maria/make_patches.py`): we ship **patches of our code only**, and the launcher applies them to the files on the player's own disc.
- **Code:** built in our CI, shipped as BPS patches against the disc files they replace, holding no game data.
- **Art and sound:** the Saturn sprites, palettes, sound effects and voices are converted from the player's disc **by the launcher**, in Python (their converters, `tools/mariasat-*.py`, `richter2-convert.py`, `charselect-convert.py`, adapted to need only Pillow, which we bundle). Not Go, Rust or Docker.
- **Checks:** each disc is identified by its files' hashes; a wrong release says which one is needed, as Maria's does.
- **Android:** the same converters run on the phone (a one-time step with the vial), or the converted files come from the PC.

## Characters in co-op
They go through everything M8 and M13 built: the lobby pick (left/right, up for the alternate), Alucard's relics unlocking their moves, the off-hand weapons (D105), the partner swap, and M12's coverage. Saturn Maria's heal (command move 1) heals partners near her too, a quarter of hers (the other project's rule).

## Acceptance criteria
1. With the three discs, all four appear in the lobby; without them, nothing changes (`launcher/test_characters.py`).
2. The release and the repository hold no Saturn or PSP data: `release.py`'s game-data check covers the new patches and converters.
3. M12's coverage for each new character: bosses (pairings with Alucard), hand weapons, relics and gates, and a playthrough segment.
4. Each new character is a partner in every pairing (M13's criterion 2).
5. The Saturn select screen shows when the Saturn disc is present and the PS1 lobby otherwise.
6. Credit for the other project in `NOTICE`, the README and the files' headers.

## Risks
- **Their overlays target SymphonyRecomp's memory layout** (base 0x8013C000, shared with RIC). Ours relinks characters into the 8MB (D7); the adaptation is the bulk of the work.
- **A Saturn disc is rare** (Japanese, Redump dumps). That's why it's optional.
- **Licence:** we follow AGPL's terms for their code (credit, source, same licence). If they relicense later, our vendored copy keeps its AGPL terms.

## Budget
About 4–6 usage windows.
