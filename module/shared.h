// Shared rooms (design/M4-shared-rooms.md).
#ifndef SHARED_H
#define SHARED_H
#include "link.h"

void SharedUpdate(void);      // once per frame, before UpdateGame
void SharedAfterUpdate(void); // once per frame, after the game's update and RenderEntities
void SharedPresence(CoopPresence* p);
void SharedHit(u8 type, u16 a, u32 b); // a partner hit event (EV_HIT / EV_HIT2)
s32 SharedRole(void);                  // ROLE_*

#endif
