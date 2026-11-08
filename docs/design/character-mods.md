# Richter and Maria from existing mods

**Status:** proposal, waiting on Tucker.

## Goal
Spend less of our own time on Richter and Maria. Where another mod already has a character working, take its code instead of writing or fixing our own, and keep only what co-op itself needs.

## What exists (read 2026-11-07)
| Mod | Characters | Form | Fits co-op? |
|---|---|---|---|
| **SOTN Ultimate** ([renanbianchi/sotn-ultimate](https://github.com/renanbianchi/sotn-ultimate), AGPL, a sotn-decomp fork at `698aab2`) | **PSP Maria** (`MARIA2.BIN`, from the same `mariapsp-forpsx` our Maria comes from, hardened for the PS1), **Saturn Maria** (`src/ric` built again with `MOD_MARIA_SAT`), **Saturn-coat Richter** (`RIC2.BIN`) | C source on the decomp, like ours | Yes, as source. It needs the Saturn and PSP discs, as M16 planned. |
| **SOTN Editor / ASS -Final-** ([pddmergilla/sotn-editor](https://github.com/pddmergilla/sotn-editor)) | **Richter Mode overhaul**: levels, growth from collecting, relic abilities, new moves, a pause-menu guide, every boss Alucard faces | A 29 KB binary patch, no source. Only on an ASS -Final- image, and it moves `RIC.BIN` into `F_GO.BIN`'s space. | Only by running their `RIC.BIN` in place of ours, which drops our co-op hooks in it. No Maria. |
| SOTN Editor's 28 vanilla hacks | A few Richter tweaks (no-flinch, Richter-style holy water) | Byte patches | Already layer and pass (`mods.py`). |

Ultimate's PSP Maria already does what three of our open bugs ask for. It has her two sub-weapon slots, maps them to the PSP's (Bible→Doll, Dagger→Cat, Axe→Cardinal, and so on), uses no in-place DRA patches, and clears its BSS on every load. That covers #169 and likely #170 and #164.

**What no mod saves us:** the co-op layer. That means the partner body (M13), the shared room, our menus and gear for them, relics teaching moves, off-hand weapons and familiars. No existing mod makes Richter or Maria play Alucard's castle with Alucard's gear. ASS's Richter Mode comes closest, but it's binary and only for ASS.

## Options
| Option | What | Cost | Verdict |
|---|---|---|---|
| **A. Ultimate as our characters' upstream** | Vendor Ultimate's Maria and Richter sources, credited, in place of our forks. Our co-op hooks stay as a thin patch on them (`characters/*/coop_*.c`). Saturn Maria and the Saturn coat come with them, which is M16 (#48) from a source that's already PS1-native. | 2–3 usage windows: re-base our hooks, rebuild, and M12's character coverage | ✅ **Recommended.** It deletes our Maria fork's bugs and gives us M16. |
| B. Co-op on a full SOTN Ultimate disc | Layer co-op onto the Ultimate disc, as with the randomizer | Large. It shifts `g_Status` by 0x14 from `saveName` on, so we'd build the module a second time against its headers. It moves stage sectors, and both players need all three discs. | ❌ Not now. Possible later as its own milestone. |
| C. ASS -Final-'s Richter Mode | Run their binary `RIC.BIN` for co-op Richter on ASS discs | Our partner build and hooks live in Richter's overlay, so this would need a hook layer in binary. It only works on ASS. | ❌ Covered as a test of the mod (#181), not as our Richter. |

**Also (Tucker, 2026-11-07):** every rebalancing change becomes an optional castle rule. Levels, Alucard's stats (#160, D178), relic moves, extra jumps, off-hand weapons and familiars already are. Under A, with all of them off, a character plays as its mod built it.

## Risks
- **Ultimate moves fast** (v1.3, forked 2026-10-14). We pin a commit and take its fixes when we choose, as with sotn-decomp.
- **Ultimate's PSP Maria links at `0x8013C000`** (RIC's slot). Ours relinks characters into the 8 MB (D7), so the relink is most of the work, as M16 found.
- **Its `g_Status` shift lives behind `MOD_SATURN`.** We build its character sources without it, and check the result against Ultimate's own build with `--same`.
- **Licence:** AGPL to AGPL, with credit in `NOTICE`, the README and the file headers.

## Acceptance criteria
1. Our PSP Maria is Ultimate's `MARIA2` code plus our co-op patch. `git diff` against the pinned Ultimate commit shows only co-op hooks.
2. #169 is fixed: two sub-weapon slots, the Bible's Doll, and the Holy Beasts (`maria_subweapons_*`).
3. Everything M12 covers for Maria still passes: bosses with Alucard, hand weapons, relics and gates, and the partner in every pairing.
4. Saturn Maria and the Saturn-coat Richter appear in the lobby when a Saturn disc is present (M16's criteria 1–6).
5. With every character rule off, Maria's moves and damage match Ultimate's own build in a scripted fight (`rules_all_off_matches_ultimate_maria`).
6. No game data in the repo or the release (`release.py`'s check).

## Questions for Tucker
1. Approve A, with Ultimate as the upstream for Richter and Maria?
2. Should M16 (#48) now come from Ultimate rather than SymphonyRecomp's ports?
