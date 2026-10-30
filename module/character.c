// Playable Richter and Maria (design/M8): which character this game's player is, and loading it.
//
// DRA's player code reads g_CoopCharacter (coop_api.h); the world keeps g_PlayableCharacter =
// Alucard, so stages, cutscenes, shops and saves see Alucard whoever plays. The character only
// changes at a load: HandleNowLoading picks the player's files (Richter's or Alucard's) at
// Play_PrepareDemo, from PL_CHARACTER, so it's set before that step and never mid-play.
//
// Maria comes from the launcher (a CharBlob in expansion RAM, link.h), our Richter from the
// disc (COOPRIC.BIN). Their files are in two parts (richter/ric.ld): the data, loaded into
// Richter's overlay slot, and the code, which the module puts in expansion RAM
// (COOP_PLAYER_FAR) once the slot is filled, zeroing their BSS after it.
#define COOP_MODULE
#include <game.h>
#include <disk.h>
#include <psxsdk/libcd.h>
#include "coop_api.h"
#include "link.h"
#include "character.h"
#include "weapons.h"
#include "message.h"
#include "offhand.h"

#define PLAYER_OVL_ADDR 0x8013C000 // RIC.BIN's address (config/splat.us.ric.yaml)
#define PLAYER_OVL_MAX (0x80180000 - PLAYER_OVL_ADDR) // the stage overlay follows
#define CdFile_SdRihVh 20 // D_800ACC74's g_LbaSdRihVh (src/dra/cd.c); its .VB comes with it

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
#define MAR_GUARDIANS_HOOK 0x8013C1F4 // her MARIA_Load, which uploads the guardians' graphics (maria/maria.ld)
static bool s_RihLoading;   // the disc is loading Richter's sound bank

// The trailer at the end of a two-part player file (richter/ric.ld).
typedef struct {
    u32 magic; // 'FAR1'
    u32 nearSize, farSize, bssSize;
    u32 farAddr; // where the code runs
} FarTrailer;
#define FAR_MAGIC 0x31524146

static const FarTrailer* Trailer(const u8* file, u32 size) {
    const FarTrailer* t = (const FarTrailer*)(file + ((size - sizeof(FarTrailer)) & ~3));

    if (size < sizeof(FarTrailer) || t->magic != FAR_MAGIC ||
        t->nearSize + t->farSize + sizeof(FarTrailer) > size || t->farAddr < COOP_PLAYER_FAR ||
        t->farAddr + t->farSize + t->bssSize > COOP_PLAYER_FAR_END) {
        return NULL;
    }
    return t;
}

// The code of a two-part file, to its far address, and its BSS zeroed.
static void PlaceFar(const u8* file, u32 size) {
    const FarTrailer* t = Trailer(file, size);
    const u32* src;
    u32* dst;
    u32 n;

    if (!t) {
        return;
    }
    src = (const u32*)(file + t->nearSize);
    dst = (u32*)t->farAddr;
    for (n = (t->farSize + 3) / 4; n--;) {
        *dst++ = *src++;
    }
    for (n = (t->bssSize + 3) / 4; n--;) {
        *dst++ = 0;
    }
    FlushCache(); // new code (D17)
}

static const CharBlob* Blob(u32 character) {
    const CharBlob* b = (const CharBlob*)CHAR_BLOB_ADDR;
    if (b->magic != CHAR_BLOB_MAGIC || b->character != character || !b->ovlSize ||
        b->ovlSize > PLAYER_OVL_MAX) {
        return NULL;
    }
    return b;
}

// DRA's sound bank addresses (libsnd is psxsdk/libsnd.h): Richter's bank is VAB 1 (g_LbaSdRihVh).
extern u32 g_VabAddrs[];
void SsVabClose(s16 vabId); // main.exe (libsnd)
#define PLAYER_VAB 1
#define VAB_CHUNK 0x800

// The blob's sound bank (Maria's voice and sounds) replaces Richter's, which the disc just
// loaded into the same VAB and the same place in sound memory (it's no bigger). One chunk a
// frame, as the game's own CD loader does (src/dra/cd.c).
static const CharBlob* s_Bank; // being sent
static u32 s_BankSent;

static void SoundBankStart(const CharBlob* b) {
    u8* vh = (u8*)(b + 1) + ((b->ovlSize + 3) & ~3);

    SsVabClose(PLAYER_VAB);
    if (SsVabOpenHeadSticky(vh, PLAYER_VAB, g_VabAddrs[PLAYER_VAB]) < 0) {
        return;
    }
    s_Bank = b;
    s_BankSent = 0;
}

static void SoundBankStep(void) {
    const CharBlob* b = s_Bank;
    u8* vb;
    u32 n;

    if (!b || (s_BankSent && (s16)SsVabTransCompleted(SS_IMEDIATE) != 1)) {
        return;
    }
    if (s_BankSent >= b->vbSize) {
        s_Bank = NULL;
        return;
    }
    vb = (u8*)(b + 1) + ((b->ovlSize + 3) & ~3) + ((b->vhSize + 3) & ~3);
    n = b->vbSize - s_BankSent < VAB_CHUNK ? b->vbSize - s_BankSent : VAB_CHUNK;
    if (SsVabTransBodyPartly(vb + s_BankSent, n, PLAYER_VAB) == -1) {
        s_Bank = NULL;
        return;
    }
    s_BankSent += n;
}

static void CopyOverlay(const CharBlob* b) {
    const u8* file = (const u8*)(b + 1);
    const FarTrailer* t = Trailer(file, b->ovlSize);
    const u32* src = (const u32*)file;
    u32* dst = (u32*)PLAYER_OVL_ADDR;
    u32 n = ((t ? t->nearSize : b->ovlSize) + 3) / 4;
    while (n--) {
        *dst++ = *src++;
    }
    PlaceFar(file, b->ovlSize); // flushes the cache too
    FlushCache();
}

// Our Richter's file, as CoopBoot read it into expansion RAM.
static const FarTrailer* RicTrailer(void) {
    return Trailer((const u8*)COOPRIC_ADDR, g_CoopRicFile.size);
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
        g_LbaBinRichter.size = RicTrailer() ? RicTrailer()->nearSize : g_CoopRicFile.size; // the slot's part
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

// Familiars for Richter and Maria (design/M8b §3): a load skips the familiar for their player
// code (src/dra/game_handlers.c), so the module loads it as the menu does when a card is on.
// From then on the game keeps it, room to room, as for Alucard.
s32 func_800E6300(void); // DRA: the familiar of the active card relic, or 0
void InitializeServant(s32 mode); // DRA
#define MENU_SWITCH_SERVANT 1     // InitializeMode (src/dra/dra.h)
static bool s_FamLoading;

static void Familiar(void) {
    s32 want;

    if (CharacterLoaded() == CHAR_ALUCARD || g_StageId == STAGE_ST0 || g_GameState != Game_Play ||
        g_GameEngineStep != Engine_Normal) {
        return;
    }
    if (s_FamLoading) {
        if (!g_IsUsingCd && g_LoadFile == CdFile_None) {
            s_FamLoading = false;
            g_ServantLoaded = g_Servant;
            InitializeServant(MENU_SWITCH_SERVANT);
        }
        return;
    }
    want = func_800E6300();
    if (!want || g_Servant || g_IsUsingCd || g_LoadFile != CdFile_None || OffhandLoading()) {
        return;
    }
    g_Servant = want;
    g_CdStep = CdStep_LoadInit;
    g_LoadFile = CdFile_ServantChr;
    g_LoadOvlIdx = want - 1;
    s_FamLoading = true;
}

// Poison water (design/M8b §2): the stage marks it (g_unkGraphicsStruct.D_8009744C), and
// Alucard's code takes 1 HP every 10 frames unless Holy Symbol is on (src/dra/692E8.c,
// HandleDamage's kind 6). Richter's and Maria's never looked: the same rule for them, down to 1
// HP (their own code decides when they die).
static void PoisonWater(void) {
    if (CharacterLoaded() != CHAR_ALUCARD && g_StageId != STAGE_ST0 && g_GameState == Game_Play &&
        g_GameEngineStep == Engine_Normal && g_unkGraphicsStruct.D_8009744C &&
        !(g_Status.relics[RELIC_HOLY_SYMBOL] & RELIC_FLAG_ACTIVE) && g_Timer % 10 == 0 &&
        g_Status.hp > 1) {
        g_Status.hp--;
    }
}

void CharacterFrame(void) {
    const CharBlob* b;

    g_CoopOptions = g_CoopLink.options; // for the player overlays

    if (g_GameState == Game_NowLoading && g_GameStep <= Play_PrepareDemo) {
        CharacterApply();
    }
    // Richter's overlay slot was just filled from the disc (the CD chain moved past it): Maria
    // over it, or our Richter's code to its far address.
    if (s_PrevLoadFile == CdFile_RichterPrg && g_LoadFile != CdFile_RichterPrg && g_StageId != STAGE_ST0) {
        if ((b = Blob(s_Loaded)) != NULL) {
            CopyOverlay(b);
        } else if (s_Loaded == CHAR_RICHTER && RicTrailer()) {
            PlaceFar((const u8*)COOPRIC_ADDR, g_CoopRicFile.size);
        }
    }
    // ...and its sound bank, once the chain that loads Richter's (SD_RIH, then SD_MAR) is done.
    if (g_LoadFile == CdFile_SdRihVh) {
        s_RihLoading = true;
    } else if (s_RihLoading && g_LoadFile == CdFile_None) {
        s_RihLoading = false;
        if (g_StageId != STAGE_ST0 && (b = Blob(s_Loaded)) != NULL && b->vhSize && b->vbSize) {
            SoundBankStart(b);
        }
    }
    SoundBankStep();
    // A hand weapon's graphics just loaded: in Maria's game they went over four of her guardians
    // (src/dra/cd.c loads them at 0x240,0x100 and 0x240,0x180, where her PS1 layout puts the owl,
    // cardinal, dragon and doll): put hers back (playtest 2026-10-25 note 4: her birds became a
    // skull and a shield).
    if ((s_PrevLoadFile == CdFile_Weapon0 || s_PrevLoadFile == CdFile_Weapon1) &&
        g_LoadFile != s_PrevLoadFile && g_StageId != STAGE_ST0) {
        WeaponLoaded(s_PrevLoadFile == CdFile_Weapon1); // for the partner to draw it (weapons.c)
    }
    if ((s_PrevLoadFile == CdFile_Weapon0 || s_PrevLoadFile == CdFile_Weapon1) &&
        g_LoadFile != s_PrevLoadFile && s_Loaded == CHAR_MARIA && g_StageId != STAGE_ST0 &&
        (b = Blob(CHAR_MARIA)) != NULL) {
        OffhandKeepSheet(s_PrevLoadFile == CdFile_Weapon1);
        (*(void (**)(void))MAR_GUARDIANS_HOOK)();
        OffhandPlaceSheet();
    }
    s_PrevLoadFile = g_LoadFile;
    // Killing Richter (BO6) freezes the game (Engine_5, unk28 0xFF) until his death scene, a stage
    // entity, lifts it. DRA's US build runs the stage's entities in that freeze only for Alucard:
    // as Richter or Maria the scene never started, and the game stayed frozen. Run them, as for
    // Alucard. Only 0xFF: other freezes (Richter's Stopwatch, 4) stop the stage on purpose.
    if (g_GameState == Game_Play && g_GameEngineStep == Engine_5 && g_unkGraphicsStruct.unk28 == 0xFF &&
        g_StageId != STAGE_ST0 && CharacterLoaded() != CHAR_ALUCARD) {
        g_api.o.UpdateStageEntities();
    }
    Familiar();
    PoisonWater();
    Growth();
}
