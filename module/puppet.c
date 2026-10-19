// The partner puppet: one textured quad per frame, built the way RenderEntities draws a
// player-sprite entity (src/dra/4B758.c), but from a CoopPresence instead of an Entity, and
// with its own VRAM slot so it never fights the game's g_PlayerDraw slots.
#define COOP_MODULE
#include <game.h>
#include "puppet.h"

extern s16** D_800A3B70[]; // DRA: per-animSet frame tables (src/dra/d_37d8.c)

// A texture page no stage on the test route uses (spike 1, see design/M1-link-presence.md);
// same in-page layout as g_PlayerDraw[0] at (0x201, 0x101), one page to the left.
#define PUPPET_VRAM_X 0x1C1
#define PUPPET_VRAM_Y 0x101
#define PUPPET_TPAGE ((PUPPET_VRAM_X >> 6) + 0x10)

#define TINT_R 0x60
#define TINT_G 0x70
#define TINT_B 0xA0

static u8* s_UploadedSprite; // sprite now in the puppet's VRAM slot

static void Upload(u8* sprite, s32 w, s32 h) {
    RECT rect;

    // Re-upload now and then anyway, in case a stage load cleared VRAM under us.
    if (sprite == s_UploadedSprite && (g_Timer & 0x1F)) {
        return;
    }
    s_UploadedSprite = sprite;
    // Same clears as RenderEntities: a 1-pixel column right of the frame and 4 rows below it,
    // so the quad's edges never show leftovers of a previous, larger frame.
    rect.x = PUPPET_VRAM_X;
    rect.y = PUPPET_VRAM_Y;
    rect.w = w / 4;
    rect.h = h;
    LoadImage(&rect, (u_long*)(sprite + 4));
    rect.x = PUPPET_VRAM_X + w / 4;
    rect.y = PUPPET_VRAM_Y - 1;
    rect.w = 1;
    rect.h = h + 4;
    ClearImage(&rect, 0, 0, 0);
    rect.x = PUPPET_VRAM_X - 1;
    rect.y = PUPPET_VRAM_Y + h;
    rect.w = w / 4 + 2;
    rect.h = 4;
    ClearImage(&rect, 0, 0, 0);
}

void DrawPuppet(const CoopPresence* p) {
    POLY_GT4* poly;
    s16* animFrame;
    u8* sprite;
    s32 pose, sheetIdx, w, h, x, y, u, v;

    // Only a same-character partner in this very room, with a sprite-sheet body frame.
    // Wolf, mist and multi-part frames are M4; other characters are M7.
    pose = p->animCurFrame & 0x7FFF;
    if (g_GameState != Game_Play || !(p->flags & PRESENCE_SPRITE) ||
        p->character != g_PlayableCharacter || p->stage != g_StageId ||
        p->roomLeft != g_Tilemap.left || p->roomTop != g_Tilemap.top ||
        p->animSet <= 0 || p->animSet >= 18 || !pose ||
        g_GpuUsage.gt4 >= MAX_POLY_GT4_COUNT) {
        return;
    }
    animFrame = D_800A3B70[p->animSet][pose];
    sheetIdx = *animFrame++;
    if (!(sheetIdx & 0x8000)) {
        return;
    }
    sheetIdx &= 0x7FFF;
    if (p->animSet == 13) {
        sprite = (*g_PlOvlAluBatSpritesheet)[sheetIdx];
    } else {
        sprite = ((u8**)SPRITESHEET_PTR)[sheetIdx];
    }
    w = sprite[0];
    h = sprite[1];
    Upload(sprite, w, h);

    x = p->x - g_Tilemap.scrollX.i.hi + g_cameraOffsetX;
    y = p->y - g_Tilemap.scrollY.i.hi + g_cameraOffsetY;
    if (x < -512 || x > 512 || y < -512 || y > 512) {
        return;
    }
    if (p->flipX & 2) {
        x -= animFrame[0] + sprite[2];
    } else {
        x += animFrame[0] + sprite[2];
    }
    y += animFrame[1] + sprite[3];
    u = (PUPPET_VRAM_X & 0x3F) * 4;
    v = PUPPET_VRAM_Y & 0xFF;

    poly = &g_CurrentBuffer->polyGT4[g_GpuUsage.gt4];
    setPolyGT4(poly);
    if (p->flipX) {
        setXY4(poly, x - w + 1, y, x + 1, y, x - w + 1, y + h, x + 1, y + h);
        setUV4(poly, u + w - 1, v, u - 1, v, u + w - 1, v + h, u - 1, v + h);
    } else {
        setXY4(poly, x, y, x + w, y, x, y + h, x + w, y + h);
        setUV4(poly, u, v, u + w, v, u, v + h, u + w, v + h);
    }
    poly->tpage = PUPPET_TPAGE;
    if (p->palette & PAL_UNK_FLAG) {
        poly->clut = g_ClutIds[p->palette & 0x7FFF];
    } else {
        poly->clut = g_ClutIds[animFrame[2] + p->palette];
    }
    if (p->blendMode) {
        setSemiTrans(poly, true);
        poly->tpage += p->blendMode & BLEND_QUARTER;
    } else {
        setSemiTrans(poly, false);
    }
    setShadeTex(poly, false);
    setRGB0(poly, TINT_R, TINT_G, TINT_B);
    setRGB1(poly, TINT_R, TINT_G, TINT_B);
    setRGB2(poly, TINT_R, TINT_G, TINT_B);
    setRGB3(poly, TINT_R, TINT_G, TINT_B);
    // One step behind the partner's own depth, so our player wins a tie.
    addPrim(&g_CurrentBuffer->ot[p->zPriority ? p->zPriority - 1 : 0], poly);
    g_GpuUsage.gt4++;
}
