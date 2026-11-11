# M20: co-op on the randomizer (#144)

The randomizer ([sotnrando](https://github.com/sotnrando/sotnrando), sotn.io) is the first, and for now the only, officially supported mod (Tucker, 2026-11-05). This narrows phase 1 of #145's proposal: no editor PPFs, no Ultimate. Double Alucard comes first; Richter and Maria follow once it holds.

## What the randomizer changes, and what that means for co-op
Measured on every preset at sotnrando `3522dc6` (`harness/mods.py`):
- **Bytes inside retail files only.** Nothing moves and nothing is added, so the disc's layout is the same, and co-op's own changes still land where they should (D34). Co-op changes 36 DRA instruction words, DRA's last sector (the boot stub), the directory, and adds files after the last one.
- **One shared instruction.** Seven presets (aperture, boss-rush, breach, chaos-lite, skinwalker, spellbound, target-confirmed) put their `FrameHook` (`jal` to its code) on the `g_PlayableCharacter` read at `0x800F30F0` that co-op also redirects. The randomizer's trampoline runs the instruction it displaced, so co-op's version goes into the trampoline instead (`layer.relocate`). Every other preset merges with no byte in common.
- **Items move by rewriting `PrizeDrops`** in each stage (`zone.items + 2 * index`). Since #154 (D172), a placed find reaches the partner as its castle flag, and the module turns the flag into an item from a table built from retail. On a randomized disc, about 300 of the 740 entries would give the wrong item. **Fix:** `layer.adapt` remakes the table from the disc's own `PrizeDrops` (positions from `patcher/collectibles.json`, offsets only) and writes it into `COOP.BIN`, where the table is tagged `COOPCLT1`. On retail it reproduces the built table exactly.
- **Relics** are found by id (`g_Status.relics`), so shared relics need nothing new. **Enemy stats, shop prices and starting gear** are each game's own data, the same on both discs.
- **Both players must use the same seed and options.** The randomizer is deterministic, so the same seed URL on the same version gives the same disc, byte for byte. HELO already refuses a different co-op disc.

## Options for the player's side
| Option | How | Verdict |
|---|---|---|
| **A. The player brings a randomized disc** | They make it on sotn.io from their own disc, as they already do. The launcher layers co-op onto it: retail (already set up) + their randomized disc + our patch, as a three-way merge on their machine | ✅ The common way to play the randomizer. Ships no data |
| B. The player brings a seed's `.ppf` | The same merge, from a PPF applied to retail first | ✅ Too, almost free once A exists (`patcher/ppf.py`) |
| C. The launcher runs the randomizer | Ship node and the randomizer, and pick a preset in the app | ❌ Not for now: a second app's UI, its updates, and its licence inside ours |

**Chosen: A, with B (D174).** The randomized disc (or `.ppf`) is a mod in a game disc (Discs & mods › Game discs, D195, which replaced D175's single randomizer setting); new castles use the game disc in use and keep it, and opening one switches to it. The seed and preset are read from what the randomizer writes on its title screen, and HELO carries them, so partners on different seeds are told both. A disc per castle was the first idea: the online joiner boots before it knows the host's castle, so it would have to restart mid-connect.

## Acceptance criteria
1. **Every preset layers.** `mods.py` builds every preset's co-op disc with no conflict, and with the collectibles table matching its own `PrizeDrops` (`patcher/test_layer.py`).
2. **Double Alucard plays a randomized castle:** on the casual and safe presets, plus one FrameHook preset, link, a shared room, a shared randomized find, and a joint save and load all pass (`mod_rando_*`).
3. **A randomized find reaches the partner as the randomizer's item,** live and after a reconnect (`rando_finds_caught_up_after_reconnect`).
4. **Different seeds are refused,** with a message on both sides that names the seed (`ui_online_rando_seed_mismatch`).
5. **The launcher makes a randomized castle** from a randomized `.cue` and from a `.ppf`, and refuses a disc it can't layer, with a message, never a crash (`ux_rando_castle`).
6. **No retail or randomizer data is shipped:** `collectibles.json` holds offsets only, and D90's check still passes.
7. Then **Richter and Maria**: the same smoke slice per pairing, in `--full`.
8. **Every preset plays:** `mods.py --test` passes each preset's smoke and finds tests, one disc at a time (a disc is 540 MB, so only casual, safe, boss-rush and lycanthrope-spr26te keep theirs). On a start-room preset, a player who walks in reaches the seed's start room and the partner can join them there (`rando_start_room_*`, #178).

## Risks
- **A new randomizer version** can add code patches that overlap ours. `mods.py` rebuilds every preset at a pinned commit. Moving the pin is a deliberate step that runs the layer test, and the launcher names the conflict instead of making a broken disc.
- **Presets that rewrite code we depend on,** such as the prologue skip, the starting room or the goals: smoke tests per preset show which ones break, and each break gets an issue.
- **Items the randomizer turns into relics, or relics into items** at boss spots use their own entities. The smoke test's find at the Cube of Zoe's spot covers one. A wider sweep is in `--full`.
