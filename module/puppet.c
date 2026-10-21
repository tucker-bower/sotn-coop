// The partner puppet: one textured quad per frame, built the way RenderEntities draws a
// player-sprite entity (src/dra/4B758.c), but from a CoopPresence instead of an Entity, and
// with its own VRAM slot so it never fights the game's g_PlayerDraw slots.
#define COOP_MODULE
#include <game.h>
#include "puppet.h"
#include "coop_api.h"
#include "link.h"
#include "character.h"

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

#define OVL_ADDR 0x8013C000 // where a player's sprite file is linked (and loaded in its own game)
#define OVL_SIZE 0x44000

// A pointer from a player sprite file, moved to where the copy is.
static u8* Rebase(u32 ptr, u32 base) {
    if (ptr < OVL_ADDR || ptr >= OVL_ADDR + OVL_SIZE) {
        return NULL;
    }
    return (u8*)(ptr - OVL_ADDR + base);
}

#define RIC_BANKS 0x8013C334 // our Richter's frame tables (richter/coop_ric.c, ric.ld)

// A partner's frame (sprite index, then offsets): DRA's tables for Alucard's animSets, Richter's
// own for his (animSet 0x8010, which his code installs into g_api.o.spriteBanks).
static s16* PartnerFrame(const CoopPresence* p, s32 pose) {
    s16** table;

    if (p->animSet > 0 && p->animSet < 18) {
        return D_800A3B70[p->animSet][pose];
    }
    if ((u16)p->animSet != 0x8010 || p->character != CHAR_RICHTER) {
        return NULL; // other overlay sets (Maria: to do)
    }
    if (CharacterLoaded() == CHAR_RICHTER) {
        return ((s16***)g_api.o.spriteBanks)[16][pose];
    }
    if (!g_CoopRicFile.size) {
        return NULL;
    }
    table = (s16**)Rebase(*(u32*)(RIC_BANKS - OVL_ADDR + PUPPET_RIC_ADDR), PUPPET_RIC_ADDR);
    return table ? (s16*)Rebase((u32)table[pose], PUPPET_RIC_ADDR) : NULL;
}

// The sprite for frame sheetIdx of a partner's animSet: from our own player's sheets if the
// partner plays the same character, else from the copies CoopBoot read (design/M8 §2).
static u8* PartnerSprite(const CoopPresence* p, s32 animSet, s32 sheetIdx) {
    u32 base;
    u8** table;

    if (p->character == CharacterLoaded()) {
        table = animSet == 13 ? *g_PlOvlAluBatSpritesheet : (u8**)SPRITESHEET_PTR;
        return table[sheetIdx];
    }
    if (p->character == CHAR_RICHTER) {
        if (!g_CoopRicFile.size) {
            return NULL;
        }
        base = PUPPET_RIC_ADDR;
    } else if (p->character == CHAR_ALUCARD) {
        base = PUPPET_ALU_ADDR;
    } else {
        return NULL; // Maria: to do
    }
    // Both files start like g_PlOvl: the bat's sheet table pointer at +4, the body's table at +0x20.
    table = animSet == 13 ? (u8**)Rebase(*(u32*)(base + 4), base) : (u8**)(base + 0x20);
    return table ? Rebase((u32)table[sheetIdx], base) : NULL;
}

// A partner Richter's palettes in another character's game (where palettes 0x120+ are someone
// else's): uploaded below the puppet's sprite, in the same free texture page.
#define RICPAL_FIRST 0x120
#define RICPAL_COUNT 16
#define RICPAL_VRAM_X 0x1C0
#define RICPAL_VRAM_Y 0x1E0

static void UploadRichterPalettes(void) {
    RECT rect;

    if ((g_Timer & 0x1F) && g_Timer > 1) { // now and then, in case a stage load cleared VRAM
        return;
    }
    rect.x = RICPAL_VRAM_X;
    rect.y = RICPAL_VRAM_Y;
    rect.w = 16;
    rect.h = RICPAL_COUNT;
    LoadImage(&rect, (u_long*)(PUPPET_RICPAL_ADDR + (RICPAL_FIRST - 0x100) * 32));
}

static u16 PartnerClut(const CoopPresence* p, s32 pal) {
    s32 y = RICPAL_VRAM_Y + (pal - RICPAL_FIRST);

    if (p->character == CHAR_RICHTER && CharacterLoaded() != CHAR_RICHTER &&
        pal >= RICPAL_FIRST && pal < RICPAL_FIRST + RICPAL_COUNT) {
        UploadRichterPalettes();
        return getClut(RICPAL_VRAM_X, y);
    }
    return g_ClutIds[pal];
}

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

    // Only a partner in this very room, with a sprite-sheet body frame. Wolf, mist and
    // multi-part frames are M4.
    pose = p->animCurFrame & 0x7FFF;
    if (g_GameState != Game_Play || !(p->flags & PRESENCE_SPRITE) ||
        !SAME_WORLD(p) || p->stage != g_StageId ||
        p->roomLeft != g_Tilemap.left || p->roomTop != g_Tilemap.top ||
        !p->animSet || !pose || g_GpuUsage.gt4 >= MAX_POLY_GT4_COUNT) {
        return;
    }
    animFrame = PartnerFrame(p, pose);
    if (!animFrame) {
        return;
    }
    sheetIdx = *animFrame++;
    if (!(sheetIdx & 0x8000)) {
        return;
    }
    sheetIdx &= 0x7FFF;
    sprite = PartnerSprite(p, p->animSet, sheetIdx);
    if (!sprite) {
        return;
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
        poly->clut = PartnerClut(p, p->palette & 0x7FFF);
    } else {
        poly->clut = PartnerClut(p, animFrame[2] + p->palette);
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
