// SOTN Co-op module: the hook table DRA jumps through, the mailbox, and presence.
#define COOP_MODULE
#include <game.h>
#include "coop_api.h"
#include "link.h"
#include "partner.h"
#include "familiar.h"
#include "message.h"
#include "arrive.h"
#include "boss.h"
#include "character.h"
#include "mist.h"
#include "carry.h"
#include "solid.h"
#include "progress.h"
#include "shared.h"
#include "spells.h"
#include "offhand.h"
#include "portrait.h"
#include "sprites.h"
#include "weapons.h"
#include "pvp.h"

bool DebugUpdate(void); // DRA
void RenderEntities(void);
void DrawMapCursor(void);

static bool UpdateHook(void);
static void RenderEntitiesHook(void);
static void DrawMapCursorHook(void);
static void StoreSaveDataHook(SaveData* save, s32 block, s32 cardIcon);
static void RenderPrimitivesHook(void);
static void PartnerHealth(void);
void RenderPrimitives(void); // DRA

// Fixed addresses: dra_hooks.ld. One jump per DRA hook.
__asm__(".section .coop-table, \"ax\"\n"
        ".set push\n.set noreorder\n"
        "j UpdateHook\nnop\n"
        "j RenderEntitiesHook\nnop\n"
        "j DrawMapCursorHook\nnop\n"
        "j StoreSaveDataHook\nnop\n"
        ".globl g_CoopCharacter\ng_CoopCharacter: .word 0\n" // coop_api.h
        ".globl g_CoopRicFile\ng_CoopRicFile: .space 24\n" // CdlFILE of COOPRIC.BIN (boot.c)
        ".globl g_CoopOptions\ng_CoopOptions: .word 0\n" // the player's OPT_* (characters/richter-ps1/coop_ric.h)
        ".globl g_CoopWeaponEntity\ng_CoopWeaponEntity: .word CoopWeaponEntity\n" // offhand.c (D105)
        "j RenderPrimitivesHook\nnop\n" // M13 (after the words above: their addresses are fixed)
        ".globl g_CoopHudCharacter\ng_CoopHudCharacter: .word 0\n" // coop_api.h
        ".set pop\n.previous");

CoopLink g_CoopLink = {COOP_MAGIC, COOP_LINK_VERSION};

static void CapturePresence(CoopPresence* p) {
    Entity* pl = &PLAYER;
    u8 plDrawFlip;

    p->flags = 0;
    p->frame = g_Timer;
    if (g_GameState != Game_Play) {
        ArrivePresence(p);
        return;
    }
    p->flags = PRESENCE_IN_PLAY;
    p->character = CharacterLoaded();
    p->stage = g_StageId;
    p->roomLeft = g_Tilemap.left;
    p->roomTop = g_Tilemap.top;
    p->x = pl->posX.i.hi + g_Tilemap.scrollX.i.hi;
    p->y = pl->posY.i.hi + g_Tilemap.scrollY.i.hi;
    p->animSet = pl->animSet;
    p->animCurFrame = pl->animCurFrame;
    p->palette = pl->palette;
    p->drawFlags = pl->drawFlags;
    p->blendMode = pl->blendMode;
    p->zPriority = pl->zPriority;
    plDrawFlip = pl->unk5A < LEN(g_PlayerDraw) ? g_PlayerDraw[pl->unk5A].flipX : 0;
    p->flipX = ((pl->facingLeft << 1) ^ plDrawFlip) | (ArriveTeleportIn() ? FLIP_TELEPORT_IN : 0) |
               ((g_CoopLink.options & OPT_SHORTCUTS) ? FLIP_SHORTCUTS : 0) |
               (ArriveSkipVote() ? FLIP_SKIP_VOTE : 0) | CarryPresence() |
               (g_GameStep != Play_Default || ArriveBusy() ? FLIP_LOADING : 0);
    if (pl->animSet && (pl->animCurFrame & 0x7FFF)) {
        p->flags |= PRESENCE_SPRITE;
    }
    if (BossHere()) {
        p->flags |= PRESENCE_BOSS;
    }
    p->aggroSwitches = BossSwitches();
    if (ArriveSharedScene()) {
        p->flags |= PRESENCE_CUTSCENE;
    }
    ArrivePresence(p);
    SharedPresence(p);
}

void SetCdVolume(s8 s_num, s16 arg1, s16 arg2); // DRA
extern s16 g_CdVolume;
void SsSetSerialVol(s16 s_num, s16 voll, s16 volr);
void SsSetMVol(s16 voll, s16 volr);
extern s16 g_SeqPlayingId, g_volumeL, g_volumeR;

// CONTROL_MUTE_MUSIC: silence the CD (XA) music, and keep it silent through the game's own
// volume changes (fades, stage changes) by setting it every frame. Unmuted, the game's own
// volume comes back. The Librarian's music isn't on the CD: it's a sequence, with its own volume.
static void MusicUpdate(void) {
    static bool muted;

    if (g_CoopLink.control & CONTROL_MUTE_MUSIC) {
        SsSetSerialVol(0, 0, 0);
        if (g_SeqPlayingId) { // SsSeqSetVol left a third of it audible: the voices' master volume
            SsSetMVol(0, 0);
        }
        muted = true;
    } else if (muted) {
        SetCdVolume(0, g_CdVolume, g_CdVolume);
        SsSetMVol(g_volumeL, g_volumeR);
        muted = false;
    }
}

// The castle's front door shuts for good behind the first player in, and with it the flag that
// keeps it shut, for both (src/st/e_castle_door.h). Whoever is still outside can't get in, however
// the door's tiles reached them, so for them it stays passable (playtest 2026-11-01).
#define DOOR_ROOM_LEFT 2
#define DOOR_ROOM_TOP 38
#define DOOR_X 105 // world x: past the door's far edge
#define DOOR_TILE_START 0x445
#define DOOR_TILE_STEP 0x20
static void CastleDoorUpdate(void) {
    static const u16 open[] = {0x6D1, 0x6D2, 0x6D3, 0x6D4, 0x6D5, 0x6D6, 0x6D3, 0x6D4};
    s32 i;

    if (g_GameState != Game_Play || g_StageId != STAGE_NO3 || g_Tilemap.left != DOOR_ROOM_LEFT ||
        g_Tilemap.top != DOOR_ROOM_TOP || !g_Tilemap.fg ||
        PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi >= DOOR_X) {
        return;
    }
    for (i = 0; i < LEN(open); i++) {
        g_Tilemap.fg[DOOR_TILE_START + i * DOOR_TILE_STEP] = open[i];
    }
}

// The buttons this game's player is moved by, for the partner's copy of them: none in a menu or
// on the map, and a scene's own steering while it holds the player (issue 151: the copy walked and
// jumped as the partner pressed buttons in their menu or through a scene).
static u32 PadDrivingPlayer(void) {
    if (g_GameEngineStep == Engine_Menu || g_GameEngineStep == Engine_Map || g_GameEngineStep == Engine_0x70) {
        return 0;
    }
    if (g_CutsceneHasControl) { // the scene's steering, as the player code reads it (src/dra/692E8.c)
        return g_Player.demo_timer ? g_Player.padSim & 0xFFFF : 0;
    }
    return g_pads[0].pressed; // spells steer with demo_timer too, from these buttons: the copy needs them
}

// Main loop, before UpdateGame. M2 applies the host's inbox here.
//
// The main loop runs UpdateGame only if DebugUpdate() returns nonzero, but in the US build
// DebugUpdate is empty (`jr ra`): it never sets a return value, and retail just happens to
// leave a nonzero v0. Returning DebugUpdate()'s "result" would return whatever our own code
// left in v0, and freeze the game whenever that's 0. So: call it, and always run the game.
static bool __attribute__((used)) UpdateHook(void) {
    g_CoopLink.heartbeat++;
    PartnerBoot();
    CharacterFrame();
    SpellsUpdate();
    // M13: the partner's copy of us runs on these: after a spell shortcut has played its input in
    g_CoopLink.selfPad = PadDrivingPlayer();
    OffhandUpdate();
    WeaponsUpdate();
    FamiliarUpdate();
    PortraitUpdate();
    MusicUpdate();
    MessageUpdate();
    if (g_CoopLink.partnerAge < 0xFFFF) {
        g_CoopLink.partnerAge++;
    }
    ProgressUpdate();
    MistStepUpdate();
    SharedUpdate();
    CastleDoorUpdate();
    BossUpdate();
    PvpUpdate();
    ProgressDamageTaken();
    DebugUpdate();
    CarryBefore();
    return ArriveFrame();
}

// The frame's RenderPrimitives: then the partner's primitives get the second bank's palettes.
static void __attribute__((used)) RenderPrimitivesHook(void) {
    u32 gt4 = g_GpuUsage.gt4, gt3 = g_GpuUsage.gt3;

    CharacterBeforePrims();
    FamiliarOwnPrims();
    RenderPrimitives();
    FamiliarOwnPrimsBack();
    PartnerAfterPrims(gt4, gt3);
}

// The save room's StoreSaveData (src/dra/62DEC.c): the game saved, so post the save.
static void __attribute__((used)) StoreSaveDataHook(SaveData* save, s32 block, s32 cardIcon) {
    CoopSaveRoomStore(save, block, cardIcon);
}

// After RenderEntities, the frame's game state is final: publish it, and draw the partner
// against it.
static void __attribute__((used)) RenderEntitiesHook(void) {
    u16 frame;

    SolidUpdateDone();
    CarryAfter();
    frame = PLAYER.animCurFrame;

    MistStepAfter();
    if (MistStepHidden()) {
        PLAYER.animCurFrame = 0; // not drawn this frame
    }
    PLAYER.animCurFrame = MAR_SAFE_FRAME(CharacterLoaded(), &PLAYER);
    OffhandRenderStart();
    CharacterRenderStart();
    FamiliarHideOwn();
    RenderEntities();
    FamiliarDrawOwn();
    CharacterRenderEnd();
    OffhandRenderEnd();
    PLAYER.animCurFrame = frame; // (the partner's frame swaps PLAYER out and back)
    PartnerFrame(); // M13: the partner's own update and drawing, after player 1's
    WeaponsDraw();
    PLAYER.animCurFrame = frame;
    SharedAfterUpdate();
    PartnerHealth();
    CapturePresence(&g_CoopLink.self);
    SpritesCapture();
    PrimsCapture();
    PvpCapture();
}

// The partner's health under this player's (issue 106): a bar, with the partner's game's own
// numbers, while it's heard from. OPT_PARTNER_HP, in Settings.
#define HP_BAR_X 8
#define HP_BAR_Y 46
#define HP_BAR_W 48
#define HP_BAR_H 3

static void Tile(s32 x, s32 y, s32 w, u8 r, u8 g, u8 b) {
    TILE* t = &g_CurrentBuffer->tiles[g_GpuUsage.tile];

    setTile(t);
    setXY0(t, x, y);
    setWH(t, w, HP_BAR_H);
    setRGB0(t, r, g, b);
    addPrim(&g_CurrentBuffer->ot[0x1F0], t);
    g_GpuUsage.tile++;
}

static void PartnerHealth(void) {
    const CoopStatus* st = (const CoopStatus*)STATUS_PARTNER_ADDR;
    s32 hp, max, w;

    if (!(g_CoopLink.options & OPT_PARTNER_HP) || g_GameState != Game_Play || st->magic != STATUS_MAGIC ||
        g_CoopLink.partnerAge > PARTNER_STALE_FRAMES || g_GpuUsage.tile + 2 >= MAX_TILE_COUNT) {
        return;
    }
    hp = ((const s32*)st->a)[1]; // g_Status.hp, hpMax
    max = ((const s32*)st->a)[2];
    if (max <= 0) {
        return;
    }
    w = hp <= 0 ? 0 : hp >= max ? HP_BAR_W : hp * HP_BAR_W / max;
    if (w) {
        Tile(HP_BAR_X, HP_BAR_Y, w, 0x30, 0xC0, 0x60);
    }
    Tile(HP_BAR_X, HP_BAR_Y, HP_BAR_W, 0x20, 0x20, 0x28);
}

// After the player's map cursor: a second, blue one on the partner's map cell. Same animation
// and geometry as the player's (DrawMapCursor, src/dra/5087C.c).
static void __attribute__((used)) DrawMapCursorHook(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    POLY_GT4* poly;
    s32 x, y, tick, size;

    DrawMapCursor();
    if (g_CoopLink.partnerAge > PARTNER_STALE_FRAMES || !(p->flags & PRESENCE_IN_PLAY) ||
        (p->stage & STAGE_INVERTEDCASTLE_FLAG) != (g_StageId & STAGE_INVERTEDCASTLE_FLAG) ||
        g_GpuUsage.gt4 >= MAX_POLY_GT4_COUNT) {
        return;
    }
    x = (p->roomLeft + (p->x >> 8)) * 4 - 14;
    y = (p->roomTop + (p->y >> 8)) * 4 - 13;
    if (g_StageId & STAGE_INVERTEDCASTLE_FLAG) {
        x -= 1;
        y -= 17;
    }
    tick = 0x3F - ((g_MapCursorTimer + 0x20) & 0x3F); // half a cycle out of phase with ours
    tick = 15 - (SQ(tick) >> 8);
    if (tick == 0) {
        tick = 15;
    }
    x += tick;
    y += tick;
    size = 32 - tick * 2;

    poly = &g_CurrentBuffer->polyGT4[g_GpuUsage.gt4];
    setPolyGT4(poly);
    setSemiTrans(poly, true);
    setShadeTex(poly, false);
    setXY4(poly, x, y, x + size, y, x, y + size, x + size, y + size);
    setUV4(poly, 0, 0, 32, 0, 0, 32, 32, 32);
    poly->tpage = 0x1A;
    poly->clut = g_ClutIds[0x170];
    setRGB0(poly, tick * 4, tick * 8, tick * 16);
    setRGB1(poly, tick * 4, tick * 8, tick * 16);
    setRGB2(poly, tick * 4, tick * 8, tick * 16);
    setRGB3(poly, tick * 4, tick * 8, tick * 16);
    addPrim(&g_CurrentBuffer->ot[OTSIZE - 1], poly);
    g_GpuUsage.gt4++;
}
