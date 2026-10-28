# M12b: off-hand weapons exactly like Alucard's (D105, D106)

**Status:** decided by Tucker (2026-10-26). **Spike passed (2026-10-26)**; building on `coop-m12-coverage`.

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

## Spike result (2026-10-26)
- **Built:** ○ creates the weapon's blueprint through DRA's own factory (`CreateEntFactoryFromEntity` + `EntityFactory`, exactly Alucard's call), and Richter's and Maria's entity loops send the children (0xE0-0xFF) to `CoopWeaponEntity` (module/offhand.c, through `g_CoopWeaponEntity` at 0x80280040). A virtual Alucard's attack animation runs on DRA's `PlayAnimation`; during each weapon entity's update `PLAYER`'s animation, pose, attack flag, draw flags and scale are his. Sprite banks 0x10-0x13 (the overlay's, and Richter's/Maria's body) are restored after; the weapon draws from bank 0x17.
- **Measured** (`m12b_offhand_like_alucard_richter` against `m12b_alucard_baseline`, the same test in Alucard's hands): all 6 classes (short sword, sword, two-handed sword, club, fist, estoc) spawn, animate, place their hitbox and end exactly as in Alucard's hands: the same slot, attack, hitbox state and hitbox per frame; timing within 1 frame. Hits: the same outcome as Alucard's per class.
- **The test's target is weak:** in the castle entrance hall neither Alucard's nor Richter's swords register a hit (the zombies rising); the hand-item test needs a better target (a still enemy, a boss).
- **Left to build:** the weapon's own palettes (it draws with one moved palette now, so multi-palette weapons are off-colour); Maria (her guardians and the weapon's tiles share VRAM: D106's window); the 1-frame timing lag; Alucard's lock-out and cancels; the hand-item test over every item; removing version 1's code.

## Build notes (2026-10-26)
- **Hits in the test:** with enemies kept at 999 HP, club, fist and estoc register hits for both Alucard and Richter; the three sword classes register none for either (the same in Alucard's own hands), so the castle entrance hall is the wrong place to test swords. The hand-item test needs another target (a boss start's boss, or Marble Gallery's armors).
- **Palettes:** every palette index (g_ClutIds, 0x300 entries) maps to a CLUT row in use, and Richter's and Maria's games leave no palette in 0x100-0x1FF empty. The off-hand keeps the weapon's main palette (the one its first frame uses) in a borrowed slot (as version 1 did); flashes and elemental tints that switch palette are off. Next: compare each class against Alucard on a contact sheet, and borrow per weapon only the palettes its frames use.
- **Maria (VRAM):** the weapon's tile sheet (256×128 px) doesn't fit the D106 window (128×224 px free). Plan: she uses one guardian at a time, so keep that guardian's graphics where they are, and put the off-hand weapon's sheet (copied to the 8MB when it loads) in the other hand's area, pointing the weapon's tpage there (0x64 ↔ 0x66). When her guardian changes, swap. Until then her off-hand weapon draws with guardian tiles.
- **Maria (2026-10-26): done.** When a weapon's sheet loads in her game it's copied to the 8MB (0x80700000), her guardians are put back, and 8 frames later (her guardians' upload is queued) the ○ hand's sheet goes in at 0x240,0x180, where her unselectable owl and doll were; the weapon draws with tpage 0x66 there. A swing filmed frame by frame (sword, Alucard / Richter / Maria): the same shapes in the same places at the same times. `m12_maria_guardians_keep_their_graphics` checks the four guardians she can select.
- **Colours:** the held-out blade is right; the raised blade (another palette of the weapon's) is blue instead of white for Richter and Maria. Open.
- **Every hand weapon (2026-10-26): passes.** `m12_hand_items_{alucard,richter,maria}`: all 72 weapons (categories short sword, sword, thrown, fist, club, two-handed), each equipped, swung at an enemy kept on its live hitbox. Richter's and Maria's results equal Alucard's item by item (spawn, hit, clean end). Two fixes found by it: factory entities a weapon starts (ids 0xED/0xEF/0xFD/0xFF, and 1) run DRA's factory, and 0xEE/0xFE DRA's entity 15, as in DRA's loop: the katanas, the brands, the Heaven Sword, the Chakram, Holbein Dagger, Jewel Sword, Marsil and the Runesword had left a factory behind forever.
- **Still open:** the palette of some frames (above); thrown items (TNT, Karma Coin: categories bomb, thrown 2) are not yet usable from the off hand.
