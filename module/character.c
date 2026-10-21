// Playable Richter and Maria (design/M8): which character this game's player is, and loading it.
//
// DRA's player code reads g_CoopCharacter (coop_api.h); the world keeps g_PlayableCharacter =
// Alucard, so stages, cutscenes, shops and saves see Alucard whoever plays. The character only
// changes at a load: HandleNowLoading picks the player's files (Richter's or Alucard's) at
// Play_PrepareDemo, from PL_CHARACTER, so it's set before that step and never mid-play.
//
// Maria and our own Richter come from the launcher (a CharBlob in expansion RAM, link.h): once
// the disc has filled Richter's overlay slot, the blob's overlay is copied over it.
#define COOP_MODULE
#include <game.h>
#include <disk.h>
#include "coop_api.h"
#include "link.h"
#include "character.h"

#define PLAYER_OVL_ADDR 0x8013C000 // RIC.BIN's address (config/splat.us.ric.yaml)
#define PLAYER_OVL_MAX (0x80180000 - PLAYER_OVL_ADDR) // the stage overlay follows

void FlushCache(void); // main.exe (PsyQ)

static u32 s_Loaded;        // CHAR_* of the player the last load brought in
static s32 s_PrevLoadFile;  // g_LoadFile last frame

static const CharBlob* Blob(u32 character) {
    const CharBlob* b = (const CharBlob*)CHAR_BLOB_ADDR;
    if (b->magic != CHAR_BLOB_MAGIC || b->character != character || !b->ovlSize ||
        b->ovlSize > PLAYER_OVL_MAX) {
        return NULL;
    }
    return b;
}

static void CopyOverlay(const CharBlob* b) {
    const u32* src = (const u32*)(b + 1);
    u32* dst = (u32*)PLAYER_OVL_ADDR;
    u32 n = (b->ovlSize + 3) / 4;
    while (n--) {
        *dst++ = *src++;
    }
    FlushCache(); // new code (D17)
}

u32 CharacterLoaded(void) {
    return g_StageId == STAGE_ST0 ? CHAR_RICHTER : s_Loaded; // the prologue is always Richter's
}

void CharacterFrame(void) {
    u32 want = g_CoopLink.character;
    const CharBlob* b;

    if (want > CHAR_MARIA) {
        want = CHAR_ALUCARD;
    }
    if (g_GameState == Game_NowLoading && g_GameStep <= Play_PrepareDemo) {
        g_CoopCharacter = want == CHAR_ALUCARD ? PLAYER_ALUCARD : PLAYER_RICHTER;
        s_Loaded = want;
    }
    // Richter's overlay slot was just filled from the disc (the CD chain moved past it).
    if (s_PrevLoadFile == CdFile_RichterPrg && g_LoadFile != CdFile_RichterPrg &&
        g_StageId != STAGE_ST0 && (b = Blob(s_Loaded)) != NULL) {
        CopyOverlay(b);
    }
    s_PrevLoadFile = g_LoadFile;
}
