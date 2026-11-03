// Hanging onto Bat Alucard, a castle rule (design/bat-carry.md).
#ifndef CARRY_H
#define CARRY_H
#include "link.h"

void CarryBefore(void);    // once per frame before UpdateGame
void CarryAfter(void);     // once per frame after it
u8 CarryPresence(void);    // FLIP_BAT and FLIP_CARRIED for this player's presence

#endif
