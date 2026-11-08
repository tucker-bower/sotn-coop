// Playable Richter and Maria (design/M8): which character this game's player is, and loading it.
//
// DRA's player code reads g_CoopCharacter (coop_api.h); the world keeps g_PlayableCharacter =
// Alucard, so stages, cutscenes, shops and saves see Alucard whoever plays. The character only
// changes at a load: HandleNowLoading picks the player's files (Richter's or Alucard's) at
// Play_PrepareDemo, from PL_CHARACTER, so it's set before that step and never mid-play.
//
// Maria comes from the launcher (a CharBlob in expansion RAM, link.h), our Richter from the
// disc (COOPRIC.BIN). Their files are in two parts (characters/richter-ps1/ric.ld): the data, loaded into
// Richter's overlay slot, and the code, which the module puts in expansion RAM
// (COOP_PLAYER_FAR) once the slot is filled, zeroing their BSS after it.
#define COOP_MODULE
#include <game.h>
#include <disk.h>
#include <sfx.h>
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
#define MAR_GUARDIANS_HOOK 0x8013C1F4 // her MARIA_Load, which uploads the guardians' graphics (characters/maria-dx/maria.ld)
static bool s_RihLoading;   // the disc is loading Richter's sound bank

// The trailer at the end of a two-part player file (characters/richter-ps1/ric.ld).
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

// The launcher's blobs, one after another (module/link.h CharBlob): one for each character in
// the session that needs one, for this game's player or the partner.
const CharBlob* CharacterBlob(u32 character) {
    const CharBlob* b = (const CharBlob*)CHAR_BLOB_ADDR;
    s32 i;

    for (i = 0; i < CHAR_BLOBS_MAX && b->magic == CHAR_BLOB_MAGIC; i++) {
        if (b->character == character) {
            return b->ovlSize && b->ovlSize <= PLAYER_OVL_MAX ? b : NULL;
        }
        b = CHAR_BLOB_NEXT(b);
    }
    return NULL;
}
#define Blob CharacterBlob

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
static s16 s_BankVab; // PLAYER_VAB (1), then 2 (Saturn Maria's second bank, over SD_MAR)

static const u8* BankVh(const CharBlob* b, s16 vab) {
    return vab == PLAYER_VAB ? (const u8*)(b + 1) + CHAR_BLOB_ALIGN(b->ovlSize) : CHAR_BLOB_VH2(b);
}

static void BankOpen(const CharBlob* b, s16 vab) {
    SsVabClose(vab);
    if (SsVabOpenHeadSticky((u8*)BankVh(b, vab), vab, g_VabAddrs[vab]) < 0) {
        s_Bank = NULL;
        return;
    }
    s_Bank = b;
    s_BankVab = vab;
    s_BankSent = 0;
}

static void SoundBankStart(const CharBlob* b) { BankOpen(b, PLAYER_VAB); }

static void SoundBankStep(void) {
    const CharBlob* b = s_Bank;
    const u8* vb;
    u32 n, size;

    if (!b || (s_BankSent && (s16)SsVabTransCompleted(SS_IMEDIATE) != 1)) {
        return;
    }
    size = s_BankVab == PLAYER_VAB ? b->vbSize : b->vb2Size;
    if (s_BankSent >= size) {
        s_Bank = NULL;
        if (s_BankVab == PLAYER_VAB && b->vh2Size && b->vb2Size) {
            BankOpen(b, 2); // then her second bank
        }
        return;
    }
    vb = BankVh(b, s_BankVab) + CHAR_BLOB_ALIGN(s_BankVab == PLAYER_VAB ? b->vhSize : b->vh2Size);
    n = size - s_BankSent < VAB_CHUNK ? size - s_BankSent : VAB_CHUNK;
    if (SsVabTransBodyPartly((u8*)vb + s_BankSent, n, s_BankVab) == -1) {
        s_Bank = NULL;
        return;
    }
    s_BankSent += n;
}

// Saturn Maria's sounds take Richter's and the prologue Maria's ids (her banks, above), so their
// priorities are hers while she's loaded: her voice 90, her effects under it, her slide 85; and
// Seiryuu's loop plays on channels 22/23, which her dragon releases. Retail for anyone else (DRA
// keeps the table for the session). SOTN Ultimate's DRA does this (cd_mod_files.h ModMarSfxPrio).
static const u16 s_SatMarSfxPrio[][3] = {
    // id, retail, Saturn Maria
    {0x6F9, 80, 90}, {0x6FA, 80, 90}, {0x6FB, 80, 90}, {0x6FC, 80, 90}, {0x702, 81, 90},
    {0x703, 81, 90}, {0x704, 81, 90}, {0x678, 40, 65}, {0x62D, 30, 65}, {0x62E, 32, 65},
    {0x6FD, 80, 60}, {0x6FE, 80, 60}, {0x700, 80, 60}, {0x6F4, 80, 60}, {0x6F5, 80, 60},
    {0x6F7, 50, 60}, {0x887, 90, 70}, {0x888, 90, 70}, {0x889, 90, 70}, {0x88A, 90, 70},
    {0x707, 40, 85}, {0x617, 30, 85},
};
extern Unkstruct_800BF554 g_SfxData[];
static void SaturnMariaSfx(bool hers) {
    s32 i;

    for (i = 0; i < LEN(s_SatMarSfxPrio); i++) {
        g_SfxData[s_SatMarSfxPrio[i][0] - 0x600].unk6 = s_SatMarSfxPrio[i][hers ? 2 : 1];
    }
    g_SfxData[0x889 - 0x600].mode = hers ? SFX_MODE_CHANNELS_22_23 : SFX_MODE_CHANNELS_12_19;
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

// Ultimate Richter's coat (launcher/saturn_richter.py, D184): his blob is retail RIC.BIN's start with
// the Saturn's coat sheet, ending ({magic, pointer} at the sheet's end) with a block of his
// recoloured palettes and the coat-sleeved whip arm, which SOTN Ultimate's DRA uploads after his
// load (cd_mod_files.h ModRicCostumeApply). Ours has no room; so it's here. The pointer is the
// block's address where the file runs (0x8013C000); `file` is where it is now.
#define RIC2_HDR_AT (0x170AC - 8)
#define RIC2_MAGIC 0x32434952 // "RIC2"
void CharacterRicCoat(const u8* file, bool partner) {
    const u32* hdr = (const u32*)(file + RIC2_HDR_AT);
    const u32* p;
    s32 n, i;
    u16 id;
    RECT rect;

    if (hdr[0] != RIC2_MAGIC) {
        return;
    }
    p = (const u32*)(file + (hdr[1] - PLAYER_OVL_ADDR));
    for (n = *p++; n > 0; n--) {
        id = *p++;
        if (!partner) { // the game's copy; a partner's palettes are only in the second bank
            for (i = 0; i < COLORS_PER_PAL; i++) {
                g_Clut[1][(id - 0x100) * COLORS_PER_PAL + i] = ((const u16*)p)[i];
            }
        }
        rect.x = (g_ClutIds[id] & 0x3F) << 4;
        rect.y = (g_ClutIds[id] >> 6) | (partner ? VRAM_BANK : 0);
        rect.w = COLORS_PER_PAL;
        rect.h = 1;
        LoadImage(&rect, (u_long*)p);
        p += COLORS_PER_PAL / 2;
    }
    for (n = *p++; n > 0; n--) {
        rect.x = ((const u16*)p)[0];
        rect.y = ((const u16*)p)[1] | (partner ? VRAM_BANK : 0);
        rect.w = ((const u16*)p)[2];
        rect.h = ((const u16*)p)[3];
        p += 2;
        LoadImage(&rect, (u_long*)p);
        p += (rect.w * rect.h + 1) / 2;
    }
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

    if (want > CHAR_LAST) {
        want = CHAR_ALUCARD;
    }
    g_CoopCharacter = want == CHAR_ALUCARD ? PLAYER_ALUCARD : PLAYER_RICHTER;
    s_Loaded = want;
    SaturnMariaSfx(want == CHAR_SAT_MARIA);
    PointRichterLoad();
}

// Richter and Maria grow like Alucard (design/M8b §4). Alucard's own code checks his EXP every
// frame (src/dra/692E8.c) and shows LEVEL UP with one of his entities; theirs never did. The
// same check here, with the module's text box for the news.
static void Growth(void) {
    static const char* const s_News[] = {NULL, "Level up!", "Max hearts up", "Max HP up"};
    u32 r;

    if (g_GameState != Game_Play || g_StageId == STAGE_ST0 || !CHAR_COOP(CharacterLoaded()) ||
        g_GameEngineStep != Engine_Normal || RULE_OFF(OPT_NO_GROWTH)) {
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

    // only the co-op characters' overlays run a familiar's entities (COOP_MARIA, COOP_RIC)
    if (!CHAR_COOP(CharacterLoaded()) || g_StageId == STAGE_ST0 || g_GameState != Game_Play ||
        g_GameEngineStep != Engine_Normal || RULE_OFF(RULE_NO_FAMILIARS)) {
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
    if (CHAR_COOP(CharacterLoaded()) && g_StageId != STAGE_ST0 && g_GameState == Game_Play &&
        g_GameEngineStep == Engine_Normal && g_unkGraphicsStruct.D_8009744C &&
        !(g_Status.relics[RELIC_HOLY_SYMBOL] & RELIC_FLAG_ACTIVE) && g_Timer % 10 == 0 &&
        g_Status.hp > 1) {
        g_Status.hp--;
    }
}

// Poison (issue 102): Alucard's rules (src/dra/71830.c, 5D5BC.c), for players whose own code has
// no such thing. A poison hit lasts his time; while it does, hits do double, attacks half (the
// mark in g_Status is his too, and coop_ric.c and coop_maria.c read it), and the player pulses
// the game's poison palette, through the hit palette's own timer. Stone and curse: not yet.
#define T_HIT_PALETTE 2 // PL_T_2, Richter's and Maria's
#define POISON_PULSE 64
#define POISON_MARK 1   // g_Status.D_80097BF8
#define POISON_LASTS 0xFFF
#define STATUS_AILMENT_POISON 0 // src/dra/dra.h
s32 GetStatusAilmentTimer(s32 statusAilment, s32 timer); // DRA (src/dra/5D5BC.c)
static s16 s_Poison;

void CharacterCurePoison(void) {
    s_Poison = 0;
    g_Status.D_80097BF8 &= ~POISON_MARK;
}

static void Poison(void) {
    if (!CHAR_COOP(CharacterLoaded()) || g_GameState != Game_Play || RULE_OFF(OPT_NO_ALUCARD_STATS) ||
        !g_Status.hp) {
        if (s_Poison) {
            CharacterCurePoison();
        }
        return;
    }
    if (g_GameEngineStep != Engine_Normal) {
        return;
    }
    if (s_Poison && PLAYER.hitParams) {
        PLAYER.hitPoints *= 2;
    }
    if (PLAYER.hitParams & ELEMENT_POISON && !(g_Status.elementsImmune & ELEMENT_POISON)) {
        s_Poison = GetStatusAilmentTimer(STATUS_AILMENT_POISON, POISON_LASTS);
    }
    if (!s_Poison) {
        return;
    }
    if (!--s_Poison) {
        CharacterCurePoison();
        return;
    }
    g_Status.D_80097BF8 |= POISON_MARK;
    if (s_Poison % POISON_PULSE == 0 && !g_Player.timers[T_HIT_PALETTE]) {
        PLAYER.palette = PAL_FLAG(PAL_CC_DARK_EFFECT);
        g_Player.timers[T_HIT_PALETTE] = POISON_PULSE / 5;
    }
}

// Alucard's health bar for Richter and Maria (issue 34). DRA draws it for g_CoopHudCharacter, from
// tiles and palettes only Alucard's F_GAME.BIN has: they're put back from CoopBoot's copy, often
// enough to outlast a load. Richter's and Maria's own bars use none of that area.
#define HUD_STRIP 28              // of F_GAME.BIN's 32x128 strips: VRAM (0x3C0, 0x100)
#define HUD_STRIP_BYTES 0x2000
#define HUD_RELOAD_EVERY 32
static void AlucardHud(void) {
    static const u8 rows[] = {0xF7, 0xF9}; // palettes 0x170-0x17F, 0x190-0x19F
    bool want = s_Loaded != CHAR_ALUCARD && g_CoopLink.options & OPT_ALUCARD_HUD;
    RECT r;
    s32 i;

    g_CoopHudCharacter = want ? PLAYER_ALUCARD : g_CoopCharacter;
    if (!want || g_GameState != Game_Play || g_Timer % HUD_RELOAD_EVERY) {
        return;
    }
    r.x = 0x3C0;
    r.y = 0x100;
    r.w = 0x20;
    r.h = 0x38;
    LoadImage(&r, (u_long*)(FGAME_GFX_ADDR + HUD_STRIP * HUD_STRIP_BYTES));
    r.x = 0;
    r.w = 0x100;
    r.h = 1;
    for (i = 0; i < 2; i++) {
        r.y = rows[i];
        LoadImage(&r, (u_long*)(FGAME_PAL_ADDR + (rows[i] - 0xF0) * 0x200));
    }
}

// Some doorways have a gap in the floor, one tile wide, that the door's walk carries Alucard
// across. Richter's and Maria's walks check for a fall: they dropped in, the wall pushed them into
// the next room and back, forever (playtest 0.14). During a door's walk at a room's edge, there's
// ground under them. A scene's walk isn't a door's.
#define DOOR_EDGE 24

static void DoorWalkGround(void) {
    s32 x = PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi;

    if (s_Loaded != CHAR_ALUCARD && g_GameState == Game_Play && g_GameStep == Play_Default &&
        g_GameEngineStep == Engine_Normal && g_Player.demo_timer && !g_CutsceneHasControl &&
        (g_Player.padSim & (PAD_LEFT | PAD_RIGHT)) &&
        (x < DOOR_EDGE || x >= (s32)(g_Tilemap.hSize << 8) - DOOR_EDGE)) {
        g_Player.vram_flag |= TOUCHING_GROUND;
    }
}

// The Outer Wall's telescope (NO1, func_us_801BA290) works when the player's status is exactly
// 0x10000000, Alucard standing. Richter's and Maria's player code also sets NO_AFTERIMAGE when
// they stand, and 0x200000 with hearts enough for a crash, so neither could ever look through it
// (#173; retail Richter neither). For them, its compare (lui v0; lui v1; lw v1, status; nop) asks
// the module instead, and the bne after it sees 0 != 1 for no. The first word is the delay slot
// of the branch before it, so the call comes one word later.
#define TELESCOPE_AT ((u32*)0x801BA3E4)
static const u32 s_TelescopeRetail[4] = {0x3C021000, 0x3C038007, 0x8C632F2C, 0x00000000};

static u32 CoopTelescopeNo(void) {
    return (g_Player.status & ~(NO_AFTERIMAGE | PLAYER_STATUS_UNK200000)) != PLAYER_STATUS_UNK10000000;
}

static void TelescopeFix(void) {
    u32 ours[4] = {0x00000000,                                             // nop (a delay slot)
                   0x0C000000 | (((u32)CoopTelescopeNo >> 2) & 0x3FFFFFF), // jal CoopTelescopeNo
                   0x00000000,                                             // nop
                   0x00001821};                                            // addu v1, zero, zero
    const u32* want;
    s32 i;

    if (g_StageId != STAGE_NO1 || g_GameState != Game_Play) {
        return;
    }
    want = CharacterLoaded() == CHAR_ALUCARD ? s_TelescopeRetail : ours;
    for (i = 0; i < 4; i++) { // only NO1's code, once it's loaded: one of the two is there
        if (TELESCOPE_AT[i] != s_TelescopeRetail[i] && TELESCOPE_AT[i] != ours[i]) {
            return;
        }
    }
    if (TELESCOPE_AT[1] != want[1]) {
        for (i = 0; i < 4; i++) {
            TELESCOPE_AT[i] = want[i];
        }
        FlushCache();
    }
}

// Ultimate Maria's HUD (characters/maria-ultimate/mar2.c CoopUltMarHud): her two sub-weapon
// icons, drawn over the sprite DRA's Richter HUD just drew. Ultimate's own DRA calls her from the
// HUD; ours has no room for that, so it's here, once the frame's HUD is done.
#define ULT_MAR_HUD_HOOK ((void (**)(void))0x8013C7F8) // characters/maria-ultimate/ult_maria.ld
// ...and Saturn Maria's own HUD, which Ultimate's DRA draws in place of Richter's
// (characters/maria-saturn/coop_sat_hud.c): hers hides his and draws itself.
#define SAT_MAR_HUD_HOOK ((void (**)(void))0x8013C588) // characters/maria-saturn/sat_maria.ld
// Saturn Maria (characters/maria-saturn) walks in steps that pass over x 0x7F-0x80, so the save
// room's walk to the save point (src/dra/62DEC.c func_80105428, step 1) paced her back and forth
// forever. Ultimate's DRA snaps her there; ours has no room, so it's here, after the frame's
// update: to the centre, with the world position along, and no step for the next frame.
#define SAVE_ROOM_ON (*(u8*)0x80137598)    // D_80137598: func_80105428 runs (src/dra/5087C.c)
#define SAVE_ROOM_STEP (*(s32*)0x801379BC) // D_801379BC: its step; 1, the walk to the centre
static void SaturnMariaSaveWalk(void) {
    s16 dx = 0x80 - PLAYER.posX.i.hi;

    if (s_Loaded == CHAR_SAT_MARIA && g_GameState == Game_Play && SAVE_ROOM_ON && SAVE_ROOM_STEP == 1 &&
        (u16)(dx + 2) < 5) {
        PLAYER.posX.i.hi += dx;
        g_PlayerX += dx;
        g_Player.padSim = 0;
    }
}

// Saturn Maria's Byakko and Seiryuu halt the game (Engine_5, unk28 4) until her own code ends the
// halt. DRA's US build runs only the stage's entities in a halt for any player but Alucard, so it
// never ended. Ultimate's DRA runs her player code there, as in the prologue; so does this, the
// prologue's way (src/dra/5087C.c, Engine_5 in ST0). DRA still runs the stage's entities after.
static void SaturnMariaHalt(void) {
    s16 x, y;

    if (s_Loaded != CHAR_SAT_MARIA || g_GameState != Game_Play || g_GameEngineStep != Engine_5 ||
        g_unkGraphicsStruct.unk28 != 4 || g_StageId == STAGE_ST0) {
        return;
    }
    x = PLAYER.posX.i.hi;
    y = PLAYER.posY.i.hi;
    g_PlOvl.D_8013C000();
    g_PlOvl.D_8013C008();
    g_PlayerX -= x - PLAYER.posX.i.hi;
    g_PlayerY -= y - PLAYER.posY.i.hi;
}

void CharacterBeforePrims(void) {
    void (*hud)(void) = *(s_Loaded == CHAR_SAT_MARIA ? SAT_MAR_HUD_HOOK : ULT_MAR_HUD_HOOK);

    SaturnMariaSaveWalk();

    if ((s_Loaded == CHAR_ULT_MARIA || s_Loaded == CHAR_SAT_MARIA) && g_StageId != STAGE_ST0 && g_GameState == Game_Play &&
        g_CoopHudCharacter != PLAYER_ALUCARD && g_LoadFile == CdFile_None &&
        (u32)hud >= COOP_PLAYER_FAR && (u32)hud < COOP_PLAYER_FAR_END) { // hers, not a load's
        hud();
    }
}

void CharacterFrame(void) {
    const CharBlob* b;

    TelescopeFix();

    // for the player overlays, with the castle's rules for them
    g_CoopOptions = g_CoopLink.options | (g_CoopLink.rulesOff & RULE_OVERLAY_MASK);
    DoorWalkGround();

    if (g_GameState == Game_NowLoading && g_GameStep <= Play_PrepareDemo) {
        CharacterApply();
    }
    // Richter's overlay slot was just filled from the disc (the CD chain moved past it): Maria
    // over it, or our Richter's code to its far address.
    if (s_PrevLoadFile == CdFile_RichterPrg && g_LoadFile != CdFile_RichterPrg && g_StageId != STAGE_ST0) {
        if ((b = Blob(s_Loaded)) != NULL) {
            CopyOverlay(b);
            if (s_Loaded == CHAR_ULT_RICHTER) { // after F_GAME2, which his load always follows
                CharacterRicCoat((const u8*)PLAYER_OVL_ADDR, false);
            }
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
        g_LoadFile != s_PrevLoadFile && CHAR_IS_MARIA(s_Loaded) && g_StageId != STAGE_ST0 &&
        (b = Blob(s_Loaded)) != NULL) {
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
    SaturnMariaHalt();
    Familiar();
    PoisonWater();
    Poison();
    Growth();
    AlucardHud();
}
