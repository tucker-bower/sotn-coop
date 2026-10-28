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
// Copies CoopBoot reads for drawing a partner who plays another character (design/M8 §2):
// our Richter (COOPRIC.BIN) and Alucard's sprites (BIN/ARC_F.BIN), each as linked at 0x8013C000.
#define PUPPET_RIC_ADDR 0x80500000
#define PUPPET_ALU_ADDR 0x80540000
#define PUPPET_RICPAL_ADDR 0x80580000 // Richter's palettes 0x100-0x13F (F_GAME2.BIN at 0x40000)
// Our Richter's and Maria's code and BSS (richter/ric.ld, maria/maria.ld): only their data is
// in Richter's overlay slot, so familiars fit after it (design/M8b §3). Each has its own
// address here (0x805C0000, 0x80600000): code rewritten at an address an emulator's recompiler
// has already compiled may not be noticed (Richter then Maria hung).
#define COOP_PLAYER_FAR 0x805C0000
#define COOP_PLAYER_FAR_END 0x80680000
#define WEAPON_SHEET_ADDR 0x80700000 // the hand weapons' tile sheets, copied out of VRAM (D106: 2 x 16KB)

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
// The player's OPT_* settings, for the player overlays (richter/coop_ric.h): mirrors the mailbox.
extern u32 g_CoopOptions;
#endif

#endif
