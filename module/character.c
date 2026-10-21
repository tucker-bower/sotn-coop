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
#include <psxsdk/libcd.h>
#include "coop_api.h"
#include "link.h"
#include "character.h"
#include "message.h"

#define PLAYER_OVL_ADDR 0x8013C000 // RIC.BIN's address (config/splat.us.ric.yaml)
#define PLAYER_OVL_MAX (0x80180000 - PLAYER_OVL_ADDR) // the stage overlay follows

void FlushCache(void); // main.exe (PsyQ)
u32 CheckAndDoLevelUp(void); // DRA: level up from EXP; 1 = level up, 2 = hearts, 3 = HP max up
typedef struct { // DRA's CdFile (src/dra/dra.h)
    s32 loc;  // sector
    s32 cb;   // CdCallbacks
    s32 size; // bytes
    u8 vabId, unkD, nextCdFileType, unkF;
} CdFile;
extern CdFile g_LbaBinRichter; // DRA: RIC.BIN's place on the disc

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

// Richter's load reads our Richter (COOPRIC.BIN) in the castle, and the retail RIC.BIN in the
// prologue (its stage is built around the retail one).
static void PointRichterLoad(void) {
    static s32 s_RetailLoc, s_RetailSize;

    if (!s_RetailLoc) {
        s_RetailLoc = g_LbaBinRichter.loc;
        s_RetailSize = g_LbaBinRichter.size;
    }
    if (s_Loaded == CHAR_RICHTER && g_StageId != STAGE_ST0 && g_CoopRicFile.size) {
        g_LbaBinRichter.loc = CdPosToInt(&g_CoopRicFile.pos);
        g_LbaBinRichter.size = g_CoopRicFile.size;
    } else {
        g_LbaBinRichter.loc = s_RetailLoc;
        g_LbaBinRichter.size = s_RetailSize;
    }
}

u32 CharacterLoaded(void) {
    return g_StageId == STAGE_ST0 ? CHAR_RICHTER : s_Loaded; // the prologue is always Richter's
}

// The host's choice becomes this game's character. Only right before a load picks the player's
// files: from a new game's NowLoading, or a joint save's (arrive.c's LoadSave, which starts
// NowLoading at Play_PrepareDemo in the same frame).
void CharacterApply(void) {
    u32 want = g_CoopLink.character;

    if (want > CHAR_MARIA) {
        want = CHAR_ALUCARD;
    }
    g_CoopCharacter = want == CHAR_ALUCARD ? PLAYER_ALUCARD : PLAYER_RICHTER;
    s_Loaded = want;
    PointRichterLoad();
}

// Richter and Maria grow like Alucard (design/M8b §4). Alucard's own code checks his EXP every
// frame (src/dra/692E8.c) and shows LEVEL UP with one of his entities; theirs never did. The
// same check here, with the module's text box for the news.
static void Growth(void) {
    static const char* const s_News[] = {NULL, "Level up!", "Max hearts up", "Max HP up"};
    u32 r;

    if (g_GameState != Game_Play || g_StageId == STAGE_ST0 || CharacterLoaded() == CHAR_ALUCARD ||
        g_GameEngineStep != Engine_Normal) {
        return;
    }
    r = CheckAndDoLevelUp();
    if (r && r < LEN(s_News)) {
        CoopMessage(s_News[r]);
    }
}

void CharacterFrame(void) {
    const CharBlob* b;

    g_CoopOptions = g_CoopLink.options; // for the player overlays

    if (g_GameState == Game_NowLoading && g_GameStep <= Play_PrepareDemo) {
        CharacterApply();
    }
    // Richter's overlay slot was just filled from the disc (the CD chain moved past it).
    if (s_PrevLoadFile == CdFile_RichterPrg && g_LoadFile != CdFile_RichterPrg &&
        g_StageId != STAGE_ST0 && (b = Blob(s_Loaded)) != NULL) {
        CopyOverlay(b);
    }
    s_PrevLoadFile = g_LoadFile;
    Growth();
}
