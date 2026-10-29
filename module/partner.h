// M13 spike: the partner as a real second player (partner.c, design/M13-partner-player.md).
#ifndef PARTNER_H
#define PARTNER_H

#define PARTNER_STALE_FRAMES 30 // no host update for this long: the partner's gone (no body)

void PartnerBoot(void);  // once, at boot: finds the BIOS's rand() seed (the partner's is its own)
void PartnerFrame(void); // after the game's update, before drawing (coop.c RenderEntitiesHook)
void PartnerDraw(void);  // after player 1's RenderEntities
bool PartnerSimulated(void); // the partner's body is the simulated one this frame (no puppet)
// A hand weapon the body can't run (its code is the partner's overlay, not ours): its swing is
// drawn from the partner's real sprites (weapons.c), moved to where the body is.
bool PartnerWeaponDiffers(s32 hand);
void PartnerBodyOffset(s16* dx, s16* dy); // the body's spot minus the partner's real one
void PartnerBankPolys(u32 gt4, u32 gt3); // what was drawn since: from the second bank (familiar.c)

#endif
