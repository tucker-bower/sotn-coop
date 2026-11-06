// Shared rooms (design/M4-shared-rooms.md).
#ifndef SHARED_H
#define SHARED_H
#include "link.h"

void SharedUpdate(void);      // once per frame, before UpdateGame
void SharedAfterUpdate(void); // once per frame, after the game's update and RenderEntities
void SharedPresence(CoopPresence* p);
void SharedHit(u8 type, u16 a, u32 b); // a partner hit event (EV_HIT / EV_HIT2)
s32 SharedRole(void);                  // ROLE_*

// Drops: the same entity ids in every stage (src/st/*/*.h)
#define E_PRIZE_DROP 3      // hearts, gold, subweapons
#define E_EQUIP_ITEM_DROP 10 // an item; params has 0x8000 when it's a placed one (EntityPersistentItemDrop)
#define IS_DROP(id) ((id) == E_PRIZE_DROP || (id) == E_EQUIP_ITEM_DROP)

#endif
