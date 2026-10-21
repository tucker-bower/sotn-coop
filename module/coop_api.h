// SOTN Co-op: the contract between DRA's COOP hooks and the co-op module.
//
// DRA has no spare room (its code and BSS end exactly where its fixed-address data begins), so
// every hook is size-neutral: under COOP, an existing call is retargeted to a same-signature
// module function that does its work and calls the original.
//
// The module is appended to DRA.BIN, so it lands right behind DRA's image. CoopBoot runs from
// there (the first call in MainGame), copies the rest to COOP_ADDR in the 8MB expansion RAM,
// and calls InitializePads. Later hooks jump through the fixed table at COOP_ADDR.
// Addresses: dra_hooks.ld (DRA's link) and coop.ld (the module's).
#ifndef COOP_API_H
#define COOP_API_H

#define COOP_ADDR 0x80280000
#define COOP_MAGIC 0x504F4F43 // 'COOP'

void CoopBoot(void);           // replaces InitializePads()
bool CoopUpdate(void);         // replaces DebugUpdate(): main loop, before UpdateGame
void CoopRenderEntities(void); // replaces RenderEntities()
void CoopDrawMapCursor(void);  // replaces DrawMapCursor()
void CoopStoreSaveData(SaveData* save, s32 block, s32 cardIcon); // replaces the save room's StoreSaveData()

// M8: the character this game's player is (PLAYER_ALUCARD / PLAYER_RICHTER; Maria runs as
// Richter's overlay). DRA's player code reads it through dra.h's PL_CHARACTER; the world keeps
// g_PlayableCharacter = PLAYER_ALUCARD, so stages, cutscenes, shops and saves see Alucard.
// A word in the module's fixed table (dra_hooks.ld).
extern s32 g_CoopCharacter;
#define PL_CHARACTER g_CoopCharacter

#ifdef COOP_MODULE
// Our Richter on the disc (COOPRIC.BIN), found by CoopBoot; size 0 if it isn't there.
extern CdlFILE g_CoopRicFile;
#endif

#endif
