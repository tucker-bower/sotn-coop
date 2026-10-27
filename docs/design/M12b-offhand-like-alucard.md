# M12b: off-hand weapons exactly like Alucard's (D105, D106)

**Status:** decided by Tucker (2026-10-26). Spike in progress on `coop-m12-coverage`.

## Goal
Richter's and Maria's off-hand (○) weapon looks, times and hits exactly as the same weapon does in Alucard's hands: its own swing animation and sprite, Alucard's wind-up and recovery, its hitboxes, its specials (Crissaegrim's multi-hit, Muramasa, Shield Rod...). Their own body keeps its pose.

## How Alucard's weapons work
- Each weapon class is an overlay (`src/weapon/w_*.c`), loaded at 0x8017A000 (right hand) or 0x8017D000 (left), with its tile sheet uploaded to VRAM (0x240,0x100 / 0x240,0x180).
- On attack, DRA starts Alucard's attack animation and spawns the weapon's entity (ids 0xE0-0xFF). The overlay's entity reads Alucard's animation frame (`PLAYER.animCurFrame`, `ext.player.anim`) to place and draw the weapon frame by frame, and to time its hitbox.

## Plan
1. **Virtual Alucard swing.** On ○, the module runs Alucard's attack animation for that weapon class on a shadow copy of the player's animation state (DRA's animation tables, same timing). During the weapon entity's update only, `PLAYER`'s animation fields are swapped for the shadow's and put back after, the way boss aggro swaps the target (D62). The body on screen stays Richter's/Maria's.
2. **Graphics through the window (D106).** The weapon's tile sheet is copied to the 8MB when it loads; each frame, the parts being drawn are uploaded into a small VRAM window and the entity's tpage points there. Maria's guardians keep their VRAM (D104's reload becomes unnecessary).
3. **Input and lock-out** as Alucard's: no attack while the swing runs, the same cancel rules.

## Spike (1 window)
Six classes: short sword, sword, two-handed sword, club, spear-like (thrust), fist. **Pass:** the weapon entity spawns, draws its frames at the hand, hits with the hand's numbers, and ends cleanly, for Richter and Maria. 5 of 6 → build it.

## Acceptance criteria
1. Every hand item works in Richter's and Maria's off hand: the M12 hand-item test (spawn, damage of its element, clean end, no crash), with a contact sheet per class.
2. The swing timing matches Alucard's within 2 frames (wind-up to first hitbox).
3. Maria's guardians stay intact with any weapon in hand (`m12_maria_guardians_keep_their_graphics`).

## Risks
- Some overlays read more of Alucard's state (MP for specials, his step machine). Mitigation: shadow those fields too, per class, found by the spike.
- The VRAM window must be free in every stage: the survey (D106) proves it first.
