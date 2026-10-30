// M15: PvP, the host's option (pvp.c, design/M15-pvp.md).
#ifndef PVP_H
#define PVP_H

void PvpCapture(void); // after RenderEntities: this player's attacks, for the partner
void PvpUpdate(void);  // before the game's update: the partner's attacks against this player

#endif
