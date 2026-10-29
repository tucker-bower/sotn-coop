// Arrive, teleport, respawn, pause rules, joint saves (design/M3-teleport-respawn-save.md).
#ifndef ARRIVE_H
#define ARRIVE_H
#include "link.h"

void Arrive(u16 stage, u16 roomId, s16 x, s16 y);
bool ArriveBusy(void);
bool SceneAftermath(void);              // a scene just ended and the game still steers the player
bool ArriveFrame(void);                 // once per frame before UpdateGame; false: skip it
void ArrivePresence(CoopPresence* p);   // adds roomId, ground position, paused/busy/dead
void CoopSaveRoomStore(SaveData* save, s32 block, s32 cardIcon);

bool ArriveTeleportIn(void); // just came in by teleport (a revive): presence says so (M13)
bool ArriveCardSaving(void); // this game's card is being written (frozen: no partner body then)

#endif
