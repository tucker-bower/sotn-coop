# M8 design: Playable Maria & Richter + Optional DXC Dialogue/Voices

**Status:** proposed 2026-10-19 (awaiting Tucker's review of design & shared-progression questions).
**Context:** D27 (character choice at New Game), D75 (M8: Maria and Richter playable from a fresh playthrough using local `sotn.pspus.iso`, plus optional DXC alternate dialogue and voice acting).

## Goal
1. **Any player can choose Alucard, Richter, or Maria** at the start of a fresh co-op playthrough (couch or online), in any combination (e.g., Alucard + Maria, Alucard + Richter, Richter + Maria, Maria + Maria).
2. **Use the USA *Dracula X Chronicles* ISO (`disks/sotn.pspus.iso`, `ULUS-10277`)** that Tucker already owns — no European PSP ISO needed.
3. **Optional DXC dialogue & voice acting:** when the player provides a DXC ISO, allow toggling between original PS1 1997 voice acting/dialogue ("What is a man?!") and the 2007 DXC script/redub.

---

## Spike findings (`disks/sotn.pspus.iso` inspection)
1. **Richter is 100% on the US PS1 disc (`sotn.us.cue`):**
   - `BIN/RIC.BIN` and `VAB/SD_RIH.VH/.VB` are already on the retail US PS1 disc and decompiled in `src/ric/`.
2. **Maria's assets in `sotn.pspus.iso` (`ULUS-10277`) match `pspeu` with an exact `-0xB780` offset shift:**
   - `D15` noted that `mods/mariapsp-forpsx` was configured for `sotn.pspeu.iso` (`ULES-00841`).
   - By inspecting the `MWo3` overlay header of `PSP_GAME/USRDIR/res/ps/PSPBIN/maria.bin` in `sotn.pspus.iso` (`base=0x09228A00, text=0x1220C, data=0x21D34`), we found that `pspus` simply omits the 5 non-English European HUD textures (`font_eu`, `hud_sp/it/ge/fr`), shifting every single Maria asset from `subweapons` (`0x1EFE0 -> 0x13860`) through `crash_cardinal_pal` (`0x3F338 -> 0x33BB8`) by a **constant `-0xB780` bytes**.
   - `PSP_GAME/USRDIR/res/ps/snd_e/SE/sd_mar2.spk` (English voice/SFX) and `sound/SE/sd_mar2.spk` (Japanese voice/SFX) are both present on `sotn.pspus.iso` and compile cleanly through `tools/maria-sfx`.
3. **DXC dialogue & voice files in `sotn.pspus.iso`:**
   - English cutscene scripts (`cutscene_script_en`) are embedded in `PSP_GAME/USRDIR/res/ps/PSPBIN/*.bin` (`st0.bin`, `cen.bin`, `dai.bin`, `dre.bin`, `lib.bin`, `no3.bin`, `no4.bin`, `sel.bin`).
   - English voice tracks are in `PSP_GAME/USRDIR/res/ps/snd_e/XA/*.at3` (and Japanese in `sound/XA/*.at3`).

---

## Architecture Options

### 1. Coexisting Alucard, Richter, and Maria on the disc
Upstream `mods/mariapsp-forpsx` overwrote `BIN/RIC.BIN` and `VAB/SD_RIH.VH/.VB` on the PS1 disc, which meant Maria *replaced* Richter. We need both Richter and Maria available simultaneously.

| Option | Idea | Verdict |
|---|---|---|
| **A. Keep retail `RIC.BIN` untouched; add `MARIA.BIN` + `SD_MAR.VH/.VB` after `COOP.BIN` (or in 8 MB RAM)** | Retail `BIN/RIC.BIN` and `VAB/SD_RIH.VH/.VB` stay at their exact retail LBAs (preserving D34). `MARIA.BIN`, `SD_MAR.VH`, and `SD_MAR.VB` are appended after `COOP.BIN` (or preloaded into the 8 MB expansion RAM at `0x80280000`). When the local player selects Maria (`char_id = 2`), the module intercepts the player overlay load (`RIC.BIN` / `SD_RIH`) and copies `MARIA.BIN` + `SD_MAR` from 8 MB RAM / CD instead. | ✅ **Recommended.** Zero retail files moved (D34 intact), both Richter and Maria work from the same disc, and loading from 8 MB RAM is instant. |
| B. Build two separate patched discs (one Richter, one Maria) | Swap discs depending on character choice | ❌ Breaks Richter + Maria co-op and doubles disc storage. |

### 2. Cross-character puppet rendering in shared rooms (`module/puppet.c`)
When Player 1 is Alucard and Player 2 is Maria (or Richter), Player 1's VRAM `0x8000` player sprite area holds Alucard's spritesheet (`F_PL00.BIN`), not Maria's or Richter's.

| Option | Idea | Verdict |
|---|---|---|
| **A. 8 MB RAM sprite cache + dynamic single-frame VRAM upload (`LoadImage`)** | Store Richter's and Maria's uncompressed 4bpp spritesheets + spritebank tables in the 8 MB expansion RAM (`0x80300000–0x80380000`). Each frame in a shared room, when `partner.character != self.character`, DMA only the partner's current pose tiles (~1–2 KB) into a reserved 64×64 VRAM slot and point the puppet `PRIM_SPRT` primitives at that slot + partner CLUT. | ✅ **Recommended.** Same technique PS1/Saturn games use for dynamic player sprites; uses ~2 KB DMA per frame and < 512 KB of our 6 MB free expansion RAM. |
| B. Squeeze all three full spritesheets into PS1 VRAM simultaneously | Keep Alucard, Richter, and Maria sheets in VRAM at all times | ❌ Impossible: PS1 VRAM is 1 MB total and stage tiles + enemy sheets fill the remaining texture pages. |

### 3. Shared progression across different characters (D27)
In vanilla SOTN:
- **Alucard** uses RPG stats, equipment, relics, and triggers story cutscenes/gates (e.g. Spike Breaker armor in Catacombs, Mist form grates, Holy Glasses cutscene in `CEN`).
- **Richter** and **Maria** start with all movement abilities (High Jump / Slide / Uppercut / Air Dash; Double Jump / Slide / Guardian Knuckle), have no equipment menu, and in vanilla Richter Mode many Alucard cutscenes/relics are disabled and certain doors are pre-opened.

| Option | Idea | Verdict |
|---|---|---|
| **A. Unified "Full Castle" world rules + cross-character pickup sharing** | Regardless of which characters are picked, the world runs the **full Alucard castle layout** (all bosses, relic orbs, item drops, and switches spawn) so a Maria+Alucard or Maria+Richter pair gets the full SOTN co-op experience:<br>- When **Richter or Maria** touches a relic orb or item pickup, they collect it and emit the `EVENT_GRANT` / `EVENT_ITEM` / `EVENT_FLAG` to their partner (so an Alucard partner receives the relic/item, and progression gates like Jewel of Open / Leap Stone / Form of Mist / Spike Breaker / Gold & Silver Rings unlock for both).<br>- Max-HP (`Life Vessel`) and Max-Heart (`Heart Vessel`) upgrades apply to all three characters; pooled gold and map exploration work identically.<br>- Alucard-only physical barriers (e.g. Mist grates when *neither* player is Alucard, or Spike Breaker corridor) open when the corresponding relic flag is owned, or Maria/Richter's invulnerability/slide moves pass through them as in `mariapsp-forpsx`. | ✅ **Recommended.** Makes mixed teams (Alucard + Maria, Maria + Richter) first-class without locking an Alucard partner out of relics/items. |
| B. Vanilla Richter-mode world when playing Richter/Maria | Disable relics, items, and story cutscenes for Richter/Maria | ❌ Breaks mixed-character co-op (a Richter/Maria player would see different room contents from an Alucard partner in shared rooms). |

### 4. Optional DXC dialogue & voice acting
| Option | Idea | Verdict |
|---|---|---|
| **A. Patcher/Launcher option when `sotn.pspus.iso` is provided** | During disc setup (or in Settings), if the user supplies `sotn.pspus.iso`:<br>- Extract Maria's overlay/assets (`MARIA.BIN`, `SD_MAR.VH/.VB`) from `sotn.pspus.iso`.<br>- Offer a toggle **Dialogue & Voices: Original 1997 (PS1) / Dracula X Chronicles (2007)**, which swaps the cutscene text tables (`cutscene_script_en`) and XA voice streams from `sotn.pspus.iso`. | ✅ **Recommended.** Legal (built locally from the user's own DXC ISO, zero game data distributed) and gives players the choice per playthrough. |

---

## Open questions for Tucker (before M8 implementation)
1. **Cross-character progression (Option 3A above):** Should mixed/non-Alucard runs keep the full Alucard castle (all relics, items, and bosses spawn so Richter/Maria can pick up relics/items for an Alucard partner and unlock progression gates), or do you want different rules when *both* players are Richter/Maria?
2. **Prologue (`ST0` Dracula fight):** When starting a New Game, should each player pick their character **before** the game starts (in the launcher / New Game character select, skipping or playing the prologue with their chosen character), or after the prologue?
3. **DXC voice/dialogue toggle:** Should the 1997 vs. 2007 dialogue/voice option be a per-playthrough setting in the launcher?

## Testable acceptance criteria (for M8)
1. **`pspus` asset extraction (`test_pspus_extract`):** extracts Maria's sprites, palettes, blueprints, and SFX from `disks/sotn.pspus.iso` (`ULUS-10277`) and builds `MARIA.BIN` + `SD_MAR.VH/.VB` with zero `pspeu` files required.
2. **Fresh-start character selection (`char_select_fresh`):** starting a fresh playthrough as Alucard, Richter, or Maria for P1 and P2 spawns each player as their chosen character in Castle Entrance (`NO0`) with working attacks, subweapons, and movement abilities.
3. **Cross-character shared room & puppets (`mixed_party_shared_room`):** Alucard + Maria and Richter + Maria in the Entrance Hall render each other's animated puppets with correct sprites/palettes and fight shared enemies together.
4. **Cross-character progression (`mixed_party_progression`):** Maria or Richter picking up a relic/item grants it to an Alucard partner over the link, and max-HP/Heart upgrades + map + castle flags sync across all character combinations.
5. **DXC dialogue option (`dxc_dialogue_toggle`):** with the DXC dialogue option enabled, cutscene scripts use the 2007 DXC text and complete without desync.
