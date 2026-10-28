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

// Another character's player file, as copied into this game (design/M8 §2): where the copy is,
// and, for the overlay characters, their frame tables and palettes (fixed places in our
// builds: richter/ric.ld, maria/maria.ld).
typedef struct {
    u32 base;      // the copy (linked at OVL_ADDR), or 0 if this game has none
    u32 banks;     // address (as linked) of the pointer to their animSet 0x8010 frame table
    u32 pals;      // their first palettes, 16 colors each (0: DRA's, as for Alucard)
    u16 palFirst;  // the palette index those are
} Foreign;

#define RICPAL_FIRST 0x120
#define MARPAL_FIRST 0x114 // PAL_MARIA (src/maria/maria.h)
#define PAL_COUNT 16
#define PAL_VRAM_X 0x1C0 // below the puppet's sprite, in the same free texture page
#define PAL_VRAM_Y 0x1E0

static bool ForeignOf(u32 character, Foreign* f) {
    const CharBlob* b = (const CharBlob*)CHAR_BLOB_ADDR;

    f->pals = 0;
    switch (character) {
    case CHAR_ALUCARD:
        f->base = PUPPET_ALU_ADDR;
        f->banks = 0;
        return true;
    case CHAR_RICHTER:
        f->base = PUPPET_RIC_ADDR;
        f->banks = 0x8013C334; // CoopRicBanks
        f->pals = PUPPET_RICPAL_ADDR + (RICPAL_FIRST - 0x100) * 32;
        f->palFirst = RICPAL_FIRST;
        return g_CoopRicFile.size != 0;
    case CHAR_MARIA: // her blob, which the launcher puts in every game where someone plays her
        if (b->magic != CHAR_BLOB_MAGIC || b->character != CHAR_MARIA) {
            return false;
        }
        f->base = (u32)(b + 1);
        f->banks = 0x8013C1F0; // CoopMarBanks
        f->pals = f->base + (0x8013C1F8 - OVL_ADDR); // maria_pal
        f->palFirst = MARPAL_FIRST;
        return true;
    }
    return false;
}

// A partner's frame (sprite index, then offsets): DRA's tables for Alucard's animSets, the
// character's own for animSet 0x8010 (which their code installs into g_api.o.spriteBanks).
static s16* PartnerFrame(const CoopPresence* p, s32 pose) {
    Foreign f;
    s16** table;

    if (p->animSet > 0 && p->animSet < 18) {
        return D_800A3B70[p->animSet][pose];
    }
    if ((u16)p->animSet != 0x8010) {
        return NULL; // their other overlay sets (weapons, guardians) aren't drawn
    }
    if (p->character == CharacterLoaded()) {
        return ((s16***)g_api.o.spriteBanks)[16][pose];
    }
    if (!ForeignOf(p->character, &f) || !f.banks) {
        return NULL;
    }
    table = (s16**)Rebase(*(u32*)Rebase(f.banks, f.base), f.base);
    return table ? (s16*)Rebase((u32)table[pose], f.base) : NULL;
}

// The sprite for frame sheetIdx of a partner's animSet: from our own player's sheets if the
// partner plays the same character, else from the copy (design/M8 §2).
static u8* PartnerSprite(const CoopPresence* p, s32 animSet, s32 sheetIdx) {
    Foreign f;
    u8** table;

    if (p->character == CharacterLoaded()) {
        table = animSet == 13 ? *g_PlOvlAluBatSpritesheet : (u8**)SPRITESHEET_PTR;
        return table[sheetIdx];
    }
    if (!ForeignOf(p->character, &f)) {
        return NULL;
    }
    // Every player file starts like g_PlOvl: the bat's sheet table pointer at +4, the body's
    // table at +0x20.
    table = animSet == 13 ? (u8**)Rebase(*(u32*)(f.base + 4), f.base) : (u8**)(f.base + 0x20);
    return table ? Rebase((u32)table[sheetIdx], f.base) : NULL;
}

// A partner's palette: in another character's game, the overlay characters' palette indexes
// hold someone else's colors, so theirs go to a spot of their own.
static u16 PartnerClut(const CoopPresence* p, s32 pal) {
    Foreign f;
    RECT rect;
    s32 y;

    if (p->character == CharacterLoaded() || !ForeignOf(p->character, &f) || !f.pals ||
        pal < f.palFirst || pal >= f.palFirst + PAL_COUNT) {
        return g_ClutIds[pal];
    }
    if (!(g_Timer & 0x1F) || g_Timer <= 1) { // now and then, in case a stage load cleared VRAM
        rect.x = PAL_VRAM_X;
        rect.y = PAL_VRAM_Y;
        rect.w = 16;
        rect.h = PAL_COUNT;
        LoadImage(&rect, (u_long*)f.pals);
    }
    y = PAL_VRAM_Y + (pal - f.palFirst);
    return getClut(PAL_VRAM_X, y);
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
