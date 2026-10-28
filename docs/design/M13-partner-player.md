# M13 design: the partner as a real second player

**Status:** proposal for Tucker's review (2026-10-27). Starts with a spike. Comparison with the other project: `research.md` → "sotn-online-coop".

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
