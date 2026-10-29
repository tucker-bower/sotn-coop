# M13 design: the partner as a real second player

**Status:** approved by Tucker (2026-10-27). Starts with a spike. Comparison with the other project: `research.md` → "sotn-online-coop".

## Goal
The partner in your game is no longer a puppet drawn from snapshots: it's a second player run by the game's own code, with the partner's own buttons. Their weapons, spells, subweapons, familiar, hit reactions and sounds all come from the game itself, for every character. This replaces M12's piece-by-piece drawing (sprites, then swings, then...) and is the base for PvP (M15) and 3+ players (M17).

## How
Each frame, after the game updates our player, the module swaps the partner's copy of "the player" into RAM, runs the player's update with the partner's buttons as pad 1, then swaps back. Drawing does the same around a second entity render. What "the player" is (from the other project's list, checked against the decomp in the spike):
- entity slots 0–63 (the player, afterimages, weapons, effects), `g_Player`, the DRA player statics, `g_PlayerDraw`, the HUD state;
- `g_Status`'s per-player part (HP, MP, hearts, stats, equipment), buff timers, the spell-input buffer;
- the two weapon overlays (0x8017A000/0x8017D000, 24 KB) and the familiar's overlay, swapped only when they differ;
- Richter's and Maria's player code, already relinked into the 8MB (D7), so any character can be the partner of any other.

The partner's state lives in the 8MB. **Only cosmetic in a shared room:** the partner's body doesn't damage enemies or pick anything up in our game; hits and pickups stay decided in the partner's own game (D57 and D51), as now.

## Options
| | Option | Verdict |
|---|---|---|
| **Input** | **A. Played-out input (recommended):** the partner's buttons arrive through the existing playout buffer and run in order; their snapshot pulls the body back if it drifts past 48 px | ✅ Deterministic for a given input stream (the harness's rule). It looks the way online already feels (Tucker: "really great"). |
| | B. Rollback: run the partner on predicted input and rewind up to 8 frames when it was wrong (the other project) | Later, only if A looks laggy. It costs up to 8× the partner's update in one frame (a problem on the Thor) and a ring of saved states. |
| **Graphics** | **A. 2 MB VRAM in our SwanStation build (recommended):** lines 512–1023 hold a private copy of the texture and palette half for each partner; while the partner runs, uploads go there and its draws set the bank bits | ✅ Every character, weapon and familiar, with no sharing. The core is ours (`bootstrap.sh`). Only the software renderer needs the patch (to confirm in the spike). |
| | B. Keep D106's window: copy the partner's graphics through the 32×224 window each frame | ❌ Too small for a whole player plus weapons and a familiar |

**VRAM is laid out once, for M17 and M19 too:** 2 MB gives one partner bank. 3+ players need a bank each, and widescreen needs a 768-wide framebuffer strip. The spike picks the layout (likely 2048×1024 or 1024×2048) so M17 and M19 don't redo it.

## Spike (first, about 1–2 windows)
Two Alucards, then Alucard + Richter, in the entrance and a boss start. Measure:
1. **Frame cost:** the partner's update and draw, as a share of a frame (target: under 25%, on the PC and the Thor).
2. **RAM:** the partner's state in the 8MB, and what's left.
3. **Determinism:** the same inputs give byte-identical RAM in two runs, and the harness's savestates hold the partner.
4. **The core patch:** a partner bank drawn correctly, and PCSX-Redux still boots the disc (it just doesn't show the partner).

Go/no-go to Tucker if a measurement misses its target.

## Game feel (in this milestone)
- **Fairy revive:** an Alucard partner in your room with the faerie out and a Life Apple in the (shared) bag revives you where you fell, instead of the D24 respawn at the partner. The Life Apple is used up.
- **Each character's own respawn effect:** Alucard comes down in the teleport's light, Richter in his cross crash, Maria in her wings or light. Shown in both games.

## Acceptance criteria
1. The spike's 4 measurements, met or decided by Tucker.
2. In every M12 shared-room, boss and hand-item test, the partner's attacks are drawn by the game's own code: `partner_pixels` finds body, weapon, subweapon and spell, for all 9 character pairings.
3. The partner's familiar shows and follows them (bat, ghost, faerie, demon, sword).
4. A partner's hit animation and sound play when the enemy in their game hits them.
5. No difference to gameplay: the M12 suite passes unchanged (the partner still can't hit enemies or take pickups in your game).
6. Fairy revive: `m13_fairy_revive` (revived in place, Life Apple gone in both games); each character's respawn effect is seen in both games (`m13_respawn_effect_*`).
7. M12's puppet code is removed, with nothing left that only it used.

## Risks
- **The swap list misses something**, and the partner leaks into our player (a buff, a sound, a camera move). The determinism test and per-feature tests catch most; it's the main risk.
- **The partner's sounds:** two players' sound effects at once. Partner sounds play quieter (a host setting).
- **The Thor's CPU:** the frame cost there decides whether Android keeps a puppet.

## Budget
About 8–12 usage windows: the spike 1–2, the swap and drawing 4–6, familiars, sound and game feel 2–3, removing the puppet 1.

## Spike notes (2026-10-27, branch `coop-m13-partner-player`)
- **Where it runs:** DRA's main loop calls `CoopUpdate()` before `UpdateGame()` and `CoopRenderEntities()` right after (`src/dra/42398.c`). The partner's frame goes in the render hook: after the game has updated player 1, before anything is drawn.
- **What gets swapped** (the other project's list, `mods/shared/CoopCore.cs` `Regions`, checked against ours): entity slots 0–63 (12 KB), `g_Player` (0x3D0), the DRA player statics 0x80137FB4–0x80138454, `g_PlayerDraw` (0x280), `D_800ACF74` (8), 0x8013B5E8 (4), `g_Status` stats (0x48) and gear (0x34), `g_PlayerHud` (0x30), `g_StatBuffTimers` (0x40), `g_ButtonCombo` (0x40): about 14.5 KB, so four copies a frame are about 58 KB. Weapon overlays (24 KB) only when the partner's weapons differ; the familiar overlay (40 KB) only when the familiars differ. Not needed here: their 208 KB player-overlay slot (our Richter and Maria live in the 8 MB area already, D7).
- **The update:** `EntityAlucard()` (0x8010A5BC) with `g_CurrentEntity = PLAYER`, then `UpdatePlayerEntities()` (0x8011A4D0), with the partner's buttons in `g_pads[0]`. No hit detection (cosmetic in a shared room, as now).
- **Drawing only the partner:** `RenderEntities()` walks all 256 slots and skips any with `animCurFrame == 0`. For the partner's pass: swap its slots 0–63 in, zero `animCurFrame` of slots 64–255 (192 halfwords, kept aside), call it, put everything back.
- **The blocker for graphics:** Alucard's current sprite is uploaded to a fixed VRAM spot each frame, so a second player's upload would overwrite the first's. That's the 2 MB VRAM patch (a private bank), or for two Alucards a second upload spot in spare VRAM. The spike measures the simulation first (frame cost, RAM, determinism), graphics second.

## Spike results (2026-10-27, `m13_spike_partner_sim`: all pass)
Two Alucards in one game, the partner run by `EntityAlucard()` and `UpdatePlayerEntities()` on scripted buttons (`module/partner.c`, behind `OPT_PARTNER_SIM`, off by default).
1. **Frame cost:** 25 scanlines on a typical frame, 33 at most: **9.5–12.5% of a frame** (target: under 25%). The first version swapped all 64 entity slots (75–88 scanlines); swapping only the slots in use on either side cut it to a third. Measured in PS1 cycles, so it's the same on the Thor's emulator.
2. **RAM:** 14.5 KB in the 8 MB area (the swapped regions).
3. **Determinism:** the same inputs give byte-identical 2 MB of RAM in two runs; savestates hold the partner (it lives in the 8 MB area).
4. **Isolation:** player 1 ends exactly where it does without the partner.
5. **Drawing two Alucards needs no VRAM patch:** `RenderEntities` uploads each player sprite frame into its `g_PlayerDraw` slot as it draws, so the partner's copy of `g_PlayerDraw` points one VRAM page left (the old puppet's page). Its drawing pass hides slots 64–255 (`animCurFrame` 0) so enemies aren't drawn twice. Screenshot: both Alucards drawn, each in its own pose.
- **Still for the 2 MB VRAM patch:** a partner of another character, and weapon and familiar graphics that differ from player 1's. The partner's sprite page overlaps D106's VRAM window (x 0x1E0–0x1FF), which the off-hand weapons use: to be laid out with the VRAM patch.
- **Go:** the approach works within budget. Next, the build proper: the partner's buttons over the link (played out, input option A), its state pulled to its snapshot past 48 px, then other characters with the VRAM bank, and removing the puppet.

## Build status and what's left (2026-10-28)
**Built** (`coop-m13-partner-player`, behind `OPT_PARTNER_SIM`, off): the simulated body (spike), the partner's buttons over the link (presence tail), the body made where the partner is in our room, dropped when they leave, pulled back past 48 px, moved with our camera; no puppet while it's drawn. Tests: `m13_spike_partner_sim`, `m13_partner_body_follows`.

**Step 1, the partner's gear (2026-10-28): done** (D124). Each host sends its player's `g_Status` ranges (stats, level, equipment; reliable, on a change, at most every 10 frames); the partner's game keeps them at `STATUS_PARTNER_ADDR` and puts them in the body before each frame (`m13_partner_status`). Attacks: the body draws its own (subweapons, spells: DRA code, right with the partner's status), and the partner's attack sprites and primitives from the link aren't placed while the body is (they would double). A hand weapon that isn't ours can't run in the body (B's overlay drops it), so the body strikes the poses and the partner's real swing is drawn from the link, moved to the body (`m13_partner_weapon_differs`, `m13_partner_weapon_same`). No overlay swapping.

**Left, in order:**
1. ~~**The partner's gear on the body.**~~ The body starts as a copy of player 1, so it holds player 1's equipment, weapons and familiar. Send the partner's equipment ids (and level and stats, for their spells and damage numbers) with a reliable event when they change; load the partner's weapon overlay (24 KB, already sent for M12's drawn swings: D106) into the body's copy of the weapon-overlay region, and swap that region too when the two players' weapons differ.
2. ~~**The VRAM bank**~~ **done 2026-10-28 (D125):** `patches/swanstation.patch` (software renderer): 1024×1024 VRAM; uploads and fills reach lines 512–1023 with y bit 9, primitives read their texture page there with texpage bit 14 and their palette with clut bit 15 (rows 512+); drawing and display stay in bank 0. States v58 (12 MB), v57 still load. Built for Linux, Windows (MinGW, `bootstrap.sh swanstation_win`) and Android (`swanstation_android`); `harness/core_check.py` gives identical hashes on Linux and Windows. The partner's player sprite now lives in the bank. M17 (more players) needs more banks or a layout within this one; M19 (widescreen) is unaffected (its framebuffer is bank 0). Original plan: **The VRAM bank** (our SwanStation build: 2 MB VRAM, lines 512–1023): needed for a partner of another character, and for weapon and familiar graphics that differ from player 1's. Lay it out once for M17 (a bank per partner) and M19 (the framebuffers): see this design's VRAM section. Software renderer only; built for Windows, Android, Linux.
3. **Richter and Maria as partners:** their player update (our overlays in the 8 MB area) in place of `EntityAlucard`, with their sprite files (already copied for the puppet).
   - **3a, a Richter partner: done (2026-10-28).**
     - **Code:** `COOPRICP.BIN` (`richter/ric_partner.ld`) is our Richter linked whole at 0x80740000, with statics of his own, read at boot together with F_GAME2.BIN (0x80680000).
     - **The partner's frames:** his `g_PlOvl` and sprite table (0x8013C000–0x8013C334) and sprite banks 16–19 are swapped in, the character is set to Richter, `Random()`'s seed is kept, and his sounds are off (step 4). He starts with his own init and runs through his own update.
     - **Graphics:** in another character's game, F_GAME2 is in VRAM's second bank, and what he draws is banked after the fact: polygons with F_GAME's texture pages or palette rows get the bank bits. That covers his body, and his primitives, drawn in a pass of their own and hidden from the game's.
     - **Leaving:** a body that leaves frees its primitives, unless a stage load already did.
     - **Test:** `m13_partner_richter` (Alucard's game, a Richter partner: his animation set, follows and animates, whip included; his graphics in bank 2; A's character and sprite banks untouched).
     - **Known gap:** PsyQ's `rand()` is a BIOS call, so its seed can't be kept. A partner's `rand()` calls shift player 1's.
   - **3b, a Maria partner: done (2026-10-28).**
     - **The partner builds:** both are compiled apart with `COOP_PARTNER` (`richter/coop_ric.h`). Their `LoadImage`/`StoreImage` go to bank 2 (`richter/coop_partner.c`), and Maria's palettes go to a `g_Clut` of her own.
     - **Maria's build:** `MARIAP.BIN` (`maria/maria_partner.ld`, 0x80780000) is made by the launcher from the DXC disc (`maria-partner.bps`) and comes in her blob (`CharBlob.partnerSize`). The module puts it in place once.
     - **Her init:** her partner init (the trailer's sixth word) is her load plus `MarInit`. Her own init also patches DRA's HUD and sound data, which would be player 1's.
     - **Queued graphics:** graphics a partner queues for DRA's loader get the bank bit in their entries.
     - **Tests:** `m13_partner_maria`, plus `m13_partner_rr`, `_rm`, `_mr`, `_mm` (Richter's and Maria's games with either partner).
   - **3c, an Alucard partner in Richter's or Maria's game: done (2026-10-28).**
     - **Code and tables:** DRA's own Alucard, started by `AluInit`. ARC_F's header and its 218 sprite and 6 bat pointers are rebased onto CoopBoot's copy and swapped in, so the header swap is now 0x388 bytes.
     - **Graphics:** his F_GAME is read at boot (strips at 0x80580000, palettes at 0x806C2000) and loaded into bank 2, with his init's palette load (op 0x16) applied there.
     - **Palettes:** DRA's palette-operation list (`D_8006C3C4`) is saved and restored around his frames, because his would work on player 1's palettes.
     - **Tests:** `m13_partner_ra`, `_ma` (his palette in bank 2 matches his own game's).
   - **All 9 pairings** run the partner's own code.
   - **Known gaps:**
     - The core's VRAM-to-CPU copy doesn't read bank 2, so a partner's death dissolve starts from player 1's frame. That's a small core patch: rebuild all three cores.
     - A partner's BIOS `rand()` calls shift player 1's.
     - The partner's off-hand items (M12b) share module state with player 1's.
4. **Familiars, sounds** (the partner's sound effects quieter), **game feel** (fairy revive, respawn effects).
5. **Turn it on, remove the puppet**, and the acceptance criteria above.
