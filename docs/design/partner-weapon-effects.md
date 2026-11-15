# The partner's weapon specials on your screen (#166)

**Status:** proposed, waiting for Tucker's approval.

## The problem
In your game, the partner's body runs the partner's player code, but never their weapon overlay (`module/partner.c`, `WeaponsOff`). There's one copy of each hand's overlay at 0x8017A000/0x8017D000, and it's yours: running the partner's weapon code there changed your swing ("a guest's weapon stopped spawning"). So the partner's weapons reach your screen only as sprites sent over the link (`weapons.c`), and only those in the weapon's first sprite set.

On 1.1.0 (harness capture, two Alucards in the Marble Gallery, QCF + □):
- **Firebrand:** the partner sees a few flames, not the fireball burst, and not the blue projectile.
- **Sword of Dawn:** the summoned soldier and the red blade don't appear.
- **Alucard Sword:** only part of the outline.
- **Subweapons** (all nine, Alucard and Richter) are already seen: they're DRA code, which the body runs. The "gem" report (Rebound Stone) doesn't reproduce.

Also lost: what isn't drawn doesn't hit. The specials' hitboxes exist only in the caster's own game.

## Options
| | How | For | Against |
|---|---|---|---|
| **A. Swap the overlays for the body (recommended)** | Each game already holds the partner's overlay copy (`WEAPON_PARTNER_ADDR`, sent for `weapons.c`). For the body's frame, swap the two 12 KB hand overlays in, run its weapon entities with the partner's code, and swap back. Its weapon sheets and 24 palettes go to the second VRAM bank, as the body's own graphics already do. | Every special, effect and hitbox is the game's own: nothing to draw by hand, and it holds for new weapons. M13 planned this swap ("only when the two players' weapons differ"). | 24 KB copied twice a frame when the weapons differ: about 10 to 15 scanlines on top of the body's 45 to 60 (D129). The body's weapon entities must also stay in its slots from frame to frame, instead of being removed. |
| B. Send the effects' primitives | Tag the weapon entities' primitives in `PrimsCapture` (as the familiar's are), draw them in the partner's game, and send the second sprite set too | No overlay running in the other game | Weapon primitives point at the caster's VRAM (sheet, palettes): every one needs remapping. 32 primitives a frame is too few for Firebrand. Still no hitboxes. |
| C. Leave it | Close as a known limit | Free | Specials are a big part of Alucard's late game, and invisible attacks read as bugs |

## Recommendation
**A.** It's the one that makes specials look and hit right, and it's what M13 meant to do. Copy only when the partner's hand items differ from yours (two Alucards with the same sword pay nothing).

## Risks
- The scanline cost when weapons differ: measure it with `mixed_soak_10min` and the frame meter. If it's too much, swap only while a weapon entity of the body's is alive.
- Overlay statics: swapping the whole overlay keeps each player's statics apart, which is exactly what failed before.
- A disc load of a weapon while the body runs: keep `WeaponsOn`'s rule of restoring only stubbed words.
- Richter's and Maria's off-hand weapons (`offhand.c`) already redirect palettes. They need the same swap, in a later step.

## Acceptance criteria
1. `partner_weapon_special_seen_alucard_and_alucard`: A uses Firebrand's, Sword of Dawn's and Alucard Sword's specials. In B's game, the body's weapon entities run with the partner's code, and B's screen near the body changes by at least 80% as many pixels as A's does near A.
2. `partner_weapon_special_hits`: a Firebrand special from the body damages an enemy in B's game, as in A's.
3. Two Alucards with the same weapons copy nothing (a counter the test reads). With different weapons, `mixed_soak_10min` and the gate's frame-cost tests stay within their limits.
4. `richter_left_hand_keeps_his_graphics` and the `partner_graphics_stay_in_their_bank_*` tests still pass: your own weapon and graphics are untouched.
