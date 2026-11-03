# M20 design: co-op on top of other mods (#144)

**Status:** proposed, for Tucker's review. Nothing is built yet.

## Goal
Players can bring the mods they already play, such as the randomizer, an editor's balance patch or SOTN Ultimate, and play them in co-op. Co-op does only co-op: shared rooms, shared progress, enemy rebalancing and the connection. Our Richter and Maria stay available by default, but they're one choice among others, not the only way to play those characters.

## Kinds of mod, and what each one breaks
Mods fall into three kinds, and each one meets our build at a different point:

| Kind | Examples | What it changes | What breaks today |
|---|---|---|---|
| **1. In-place patches** | [SotN Randomizer](https://github.com/3snowp7im/SotN-Randomizer) (sotn.io), [SOTN Editor](https://pddmergilla.github.io/sotn-editor/) PPFs (stats, drops, shops, rooms), most classic hacks | Bytes inside retail files, at the same disc positions. The randomizer's writes are mostly data (item and relic placement, drops, stats), plus about 40 small code patches written straight into the disc image | Only our installer. The co-op patch is a BPS of the **whole retail image** and refuses any other disc (`patcher.py check_disc`). Our hooks, the module and the network would mostly work as they are |
| **2. Rebuilt from source** | [SOTN Ultimate](https://github.com/renanbianchi/sotn-ultimate) (sotn-decomp fork: Saturn and PSP content, Saturn and PSP Maria, new stages) | DRA recompiled (its code moves), `g_Status` grown (fields from `saveName` on move by 0x14), new stage slots, 18 new disc files, a new save format | Everything: our DRA hooks are word patches at retail addresses, the module links against retail addresses, `overlay_table.c` comes from retail overlays |
| **3. Characters** | Ultimate's Saturn and PSP Maria, a player's own Richter edit | A player overlay (`RIC.BIN`, `MARIA.BIN`) and its art | The partner's body needs that character's sprites and animation tables (M8, M13). Today it knows only ours |

Two things already work in our favour:
- **Our disc keeps every retail file where it was** (D34) and puts our files after the last one. Kind 1 patches address the disc by fixed position, so they still land in the right place on a co-op disc.
- **Both players must have the same disc.** `HELO` already compares the co-op disc's CRC, so two different randomizer seeds, or a mod on one side only, are refused at connect.

## Options
| Option | What it is | Covers | Cost | Verdict |
|---|---|---|---|---|
| **A. Layer co-op onto any in-place-modded disc** | The installer stops patching a whole image. It applies our changes file by file: it checks that each DRA hook site still holds the retail instruction, adds `COOP.BIN` and the character files after the last file, and updates the disc's directory. A **compatibility check** reports, for any disc: retail, a known mod release, compatible, or not, with the reason (for example "the randomizer's patch X changed hook site Y"). At boot, the module checks its hook sites and key addresses and shows a message instead of crashing | Kind 1: the randomizer, editor PPFs, classic hacks | 2–3 windows | ✅ **Phase 1** |
| **B. Co-op builds of decomp-based mods** | For a mod built on sotn-decomp, apply `patches/sotn-decomp.patch` (about 330 lines, all retargeted calls) to **its** source, compile the module against **its** headers and symbol map, and regenerate the overlay table from its overlays. Ultimate's builder makes the same disc for everyone (it checks a release MD5), so we can ship one small patch keyed to that disc: "Ultimate 1.3 → Ultimate 1.3 + co-op". The launcher recognises the disc by its hash | Kind 2, one mod release at a time. Ultimate first | 3–5 windows for the Ultimate pilot, then about 1 per mod release | ✅ **Phase 2** (pilot) |
| **C. A co-op SDK in sotn-decomp itself** | Upstream the hook sites as an opt-in build switch (`COOP=1`) under sotn-decomp's `mods/` convention, with a documented module ABI. Any decomp mod turns co-op on and builds it, with no fork-by-fork work from us | Kind 2 in general, maintained by mod authors | Open-ended, and needs upstream maintainers to agree | ⏳ Later, once B shows the hook set holds up on a real mod |
| D. Find addresses at run time | Find the game's functions and data by searching for byte signatures at boot, so one `COOP.BIN` adapts to moved code | Kind 2 in theory | Very high, fragile, and silent when wrong | ❌ |

**Characters (kind 3).** Our Richter and Maria stay as the defaults. A character from a mod is used as that mod ships it, in the player's own game, through B. The work left is the partner's body: a **character contract**, meaning the overlay file, where its sprites and palettes come from, and its animation tables, with ours as the first two entries. That gets its own design once the Ultimate pilot shows what Saturn Maria needs. **M16 (Saturn characters) is better replaced by B:** Ultimate already brings Saturn Maria and the PSP content to the PS1, maintained by its author.

## Recommendation
1. **Phase 1 (A), with the randomizer first.** It's the largest SOTN community, and it's all kind 1. Then editor PPFs.
2. **Phase 2 (B), an Ultimate pilot.** It's AGPL like us, built on sotn-decomp, gives deterministic discs, and its developer notes are thorough.
3. **Phase 3 (C)** only if the pilot shows the hook set works on a mod we didn't write.

Timing: after v1.0. Nothing here is needed for 1.0, and the installer change touches every player.

### First steps (spikes, before any build)
- Run the randomizer's CLI on the dev disc. Diff which files and words it changes against our hook sites and against what the module reads (teleport table, item tables, enemy definitions).
- Apply a randomizer PPF to a **co-op** disc, which may already work because of D34. Then play one smoke session.
- Build Ultimate 1.3 from source with `patches/sotn-decomp.patch` applied, and list what doesn't compile or link.

## Acceptance criteria
1. **Compatibility check:** it classifies retail, a randomizer seed, an editor PPF, Ultimate 1.3, and a disc with a changed hook site (incompatible, with the reason). Covered by `patcher/test_compat.py` against discs the harness builds locally.
2. **Randomizer co-op:** on one seed's disc, a co-op smoke slice passes. That's connect, a shared room, a boss pull, progression shared (a randomized relic picked up by one player unlocks for both), and a joint save and load.
3. **Mismatched discs are refused** (two seeds, or mod versus retail), with a clear message on both sides: `ui_online_*` cases.
4. **Editor PPF:** co-op enemy rebalancing applies to the modded values, not the retail ones (a test reads a changed enemy's HP).
5. **Ultimate pilot:** the same smoke slice on Ultimate 1.3 + co-op, plus a room in a Saturn-only stage shared by both players, and a save and load in its save format.
6. **A disc we can't support** shows a message at install and at boot, never a crash or a hang.
7. **Nothing we ship holds retail or mod data:** D90's check extends to patches made against a mod's disc.

## Risks
- **The randomizer's code patches may touch our hook sites**, or data the module relies on. The spike answers this. A conflict is fixed per hook (moving it to another retargetable call) or reported by the compatibility check.
- **Silent breakage on discs we haven't seen.** Kind 1 mods we never tested could change code the module calls. The boot check covers the hook sites and the module's key addresses, but not everything.
- **The test matrix grows** with each supported mod. Keep to one smoke slice per mod in `--full`. Fixtures are built locally from each mod's disc, never shipped.
- **Ultimate's `g_Status` shift** moves offsets that our harness, mailbox decoding and F9 reports read. Under B, these come from that build's symbol map, not fixed numbers.
- **Maintenance:** each new Ultimate release needs a co-op rebuild. Until one exists, the launcher says "this version of Ultimate isn't supported yet".
- **Legal:** a patch made against a mod's disc must carry only our code: no retail data and no mod data (Ultimate's Saturn and PSP conversions).

## Decisions needed (Tucker)
1. Go with Phase 1 (randomizer, then editor PPFs) and the Ultimate pilot, after v1.0?
2. Replace M16 (our Saturn characters) with "Ultimate + co-op"?
3. Should we contact Ultimate's author and sotn-decomp's maintainers (for B's pilot and later C)? That's outward-facing, so it's your call, and it's best done by you.
