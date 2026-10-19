// Arrive, teleport, respawn, pause rules, joint saves (design/M3-teleport-respawn-save.md).
#ifndef ARRIVE_H
#define ARRIVE_H
#include "link.h"

void Arrive(u16 stage, u16 roomId, s16 x, s16 y);
bool ArriveBusy(void);
bool ArriveFrame(void);                 // once per frame before UpdateGame; false: skip it
void ArrivePresence(CoopPresence* p);   // adds roomId, ground position, paused/busy/dead
void CoopSaveRoomStore(SaveData* save, s32 block, s32 cardIcon);

#endif
