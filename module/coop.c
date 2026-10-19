// SOTN Co-op module: the hook table DRA jumps through, the mailbox, and presence.
#define COOP_MODULE
#include <game.h>
#include "coop_api.h"
#include "link.h"
#include "arrive.h"
#include "progress.h"
#include "puppet.h"
#include "shared.h"

bool DebugUpdate(void); // DRA
void RenderEntities(void);
void DrawMapCursor(void);

static bool UpdateHook(void);
static void RenderEntitiesHook(void);
static void DrawMapCursorHook(void);
static void StoreSaveDataHook(SaveData* save, s32 block, s32 cardIcon);

// Fixed addresses: dra_hooks.ld. One jump per DRA hook.
__asm__(".section .coop-table, \"ax\"\n"
        ".set push\n.set noreorder\n"
        "j UpdateHook\nnop\n"
        "j RenderEntitiesHook\nnop\n"
        "j DrawMapCursorHook\nnop\n"
        "j StoreSaveDataHook\nnop\n"
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
    p->character = g_PlayableCharacter;
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
    p->flipX = (pl->facingLeft << 1) ^ plDrawFlip;
    if (pl->animSet && (pl->animCurFrame & 0x7FFF)) {
        p->flags |= PRESENCE_SPRITE;
    }
    ArrivePresence(p);
    SharedPresence(p);
}

// Main loop, before UpdateGame. M2 applies the host's inbox here.
//
// The main loop runs UpdateGame only if DebugUpdate() returns nonzero, but in the US build
// DebugUpdate is empty (`jr ra`): it never sets a return value, and retail just happens to
// leave a nonzero v0. Returning DebugUpdate()'s "result" would return whatever our own code
// left in v0, and freeze the game whenever that's 0. So: call it, and always run the game.
static bool __attribute__((used)) UpdateHook(void) {
    g_CoopLink.heartbeat++;
    if (g_CoopLink.partnerAge < 0xFFFF) {
        g_CoopLink.partnerAge++;
    }
    ProgressUpdate();
    SharedUpdate();
    DebugUpdate();
    return ArriveFrame();
}

// The save room's StoreSaveData (src/dra/62DEC.c): the game saved, so post the save.
static void __attribute__((used)) StoreSaveDataHook(SaveData* save, s32 block, s32 cardIcon) {
    CoopSaveRoomStore(save, block, cardIcon);
}

// After RenderEntities, the frame's game state is final: publish it, and draw the partner
// against it.
static void __attribute__((used)) RenderEntitiesHook(void) {
    RenderEntities();
    SharedAfterUpdate();
    CapturePresence(&g_CoopLink.self);
    if (g_CoopLink.partnerAge <= PARTNER_STALE_FRAMES) {
        DrawPuppet(&g_CoopLink.partner);
    }
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
