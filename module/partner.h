// M13 spike: the partner as a real second player (partner.c, design/M13-partner-player.md).
#ifndef PARTNER_H
#define PARTNER_H

void PartnerFrame(void); // after the game's update, before drawing (coop.c RenderEntitiesHook)
void PartnerDraw(void);  // after player 1's RenderEntities
bool PartnerSimulated(void); // the partner's body is the simulated one this frame (no puppet)

#endif
