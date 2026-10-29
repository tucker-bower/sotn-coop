// M13 step 4: the partner's familiar on this screen (design/M13-partner-player.md). The familiar
// runs in the partner's own game (its overlay is one per game, at 0x80170000): its sprites and
// primitives come with presence (sprites.c's capture), and this game draws them beside the
// partner's body, from a copy of its overlay's frame table and its graphics in VRAM's second bank
// (the weapons' way: weapons.c). Each game copies its familiar when it loads; the host sends it.
#define COOP_MODULE
#include <game.h>
#include "link.h"
#include "partner.h"
#include "familiar.h"

void RenderEntities(void);   // DRA
void RenderPrimitives(void); // DRA

#define FAMILIAR_PRG 0x80170000
#define FAM_BANK 0x14  // the familiars' sprite bank (ANIMSET_OVL(0x14))
#define FAM_FRAMES 256 // frames in its table, at most
#define SHEET_X 0x2C0  // where DRA loads its graphics (src/dra/cd.c: LoadTPage)
#define SHEET_Y 0x100
#define PAL_FIRST 0x140
#define N_PAL (FAMILIAR_CLUT_SIZE / 32)
#define COPY_DELAY 30 // frames after it loads: its init uploads its palettes

static CoopFamiliar* Self(void) { return (CoopFamiliar*)FAMILIAR_SELF_ADDR; }
static const CoopFamiliar* Partner(void) { return (const CoopFamiliar*)FAMILIAR_PARTNER_ADDR; }

static s32 s_Have = -1; // g_ServantLoaded when this game's copy was made
static s16 s_CopyIn;

static void Sheet(u16* dst, bool store) {
    RECT r;

    r.x = SHEET_X;
    r.y = SHEET_Y | (store ? 0 : VRAM_BANK);
    r.w = 0x40;
    r.h = 0x80;
    DrawSync(0);
    store ? StoreImage(&r, (u_long*)dst) : LoadImage(&r, (u_long*)dst);
    r.y = (SHEET_Y + 0x80) | (store ? 0 : VRAM_BANK);
    r.w = 0x20;
    DrawSync(0);
    store ? StoreImage(&r, (u_long*)(dst + 0x40 * 0x80)) : LoadImage(&r, (u_long*)(dst + 0x40 * 0x80));
    DrawSync(0);
}

// This game's: once per frame. A copy a little after a familiar loads (or none, when it goes).
void FamiliarUpdate(void) {
    CoopFamiliar* f = Self();

    if (g_GameState != Game_Play || g_IsUsingCd) {
        return;
    }
    if ((s32)g_ServantLoaded != s_Have) {
        s_Have = g_ServantLoaded;
        s_CopyIn = COPY_DELAY;
    }
    if (!s_CopyIn || --s_CopyIn) {
        return;
    }
    f->servant = s_Have;
    if (s_Have) {
        __builtin_memcpy(f->ovl, (const void*)FAMILIAR_PRG, FAMILIAR_OVL_SIZE);
        Sheet(f->sheet, true);
        __builtin_memcpy(f->clut, (u16*)g_Clut + PAL_FIRST * COLORS_PER_PAL, FAMILIAR_CLUT_SIZE);
        f->bank = ((u32*)g_api.o.spriteBanks)[FAM_BANK];
    }
    f->magic = FAMILIAR_MAGIC;
    f->seq++;
}

// --- the partner's -------------------------------------------------------------------------
static u32 s_Seen;  // the partner's copy in the second bank (its seq + 1; 0: none)
static u32 s_Table[FAM_FRAMES]; // its frame table, rebased onto the copy

void FamiliarReload(void) { s_Seen = 0; }

static bool Ready(void) {
    const CoopFamiliar* f = Partner();
    const u32* table;
    u32 k, v, delta = (u32)f->ovl - FAMILIAR_PRG;
    RECT r;

    if (f->magic != FAMILIAR_MAGIC || !f->servant) {
        return false;
    }
    if (s_Seen == f->seq + 1) {
        return true;
    }
    // its frame table (the sword has none: it's primitives, and its bank is someone else's)
    table = (const u32*)(f->bank + delta);
    for (k = 0; k < FAM_FRAMES; k++) {
        v = f->bank >= FAMILIAR_PRG && (u32)&table[k] < (u32)f->ovl + FAMILIAR_OVL_SIZE ? table[k] : 0;
        s_Table[k] = v >= FAMILIAR_PRG && v < FAMILIAR_PRG + FAMILIAR_OVL_SIZE ? v + delta : 0;
    }
    Sheet((u16*)f->sheet, false);
    for (k = 0; k < N_PAL; k++) {
        u16 clut = g_ClutIds[PAL_FIRST + k];
        r.x = (clut & 0x3F) * 16;
        r.y = ((clut >> 6) & 0x1FF) | VRAM_BANK;
        r.w = 16;
        r.h = 1;
        LoadImage(&r, (u_long*)(f->clut + k * COLORS_PER_PAL));
        DrawSync(0);
    }
    s_Seen = f->seq + 1;
    return true;
}

u32 g_CoopFamiliarDrawn; // its sprites and primitives drawn last frame (tests read it: coop.map)

// Its primitives (the sword's): replayed in a pool of this game's own (as sprites.c's, allocated
// once per stage), drawn in a pass of their own from the second bank, hidden from the game's.
#define FAM_PRIMS 16
#define FAM_MARK 0xC6 // the pool's mark in each one's p3 (sprites.c's way)
static s16 s_Pool = -1;

static bool PoolIntact(void) {
    Primitive* p;
    s32 k;

    if (s_Pool < 0) {
        return false;
    }
    for (k = 0, p = &g_PrimBuf[s_Pool]; k < FAM_PRIMS; k++, p = p->next) {
        if (!p || p->type == PRIM_NONE || p->p3 != FAM_MARK) {
            return false;
        }
    }
    return true;
}

static s32 DrawPrims(s16 dx, s16 dy) {
    static u8 s_Shown[MAX_PRIM_COUNT];
    u32 gt4 = g_GpuUsage.gt4, gt3 = g_GpuUsage.gt3;
    Primitive* p;
    s32 i, k, n = 0;

    if (!PoolIntact()) {
        s_Pool = g_api.AllocPrimitives(PRIM_GT4, FAM_PRIMS);
        if (s_Pool < 0) {
            return 0;
        }
    }
    p = &g_PrimBuf[s_Pool];
    for (k = 0; k < (s32)g_CoopLink.partnerPrimCount && p; k++) {
        const u8* q = g_CoopLink.partnerPrims[k];
        if (q[PRIM_TAG] != FAMILIAR_TAG || q[3] == PRIM_NONE) {
            continue;
        }
        {
            Primitive* next = p->next;
            __builtin_memcpy((u8*)p + 4, q, COOP_PRIM_SIZE);
            p->next = next;
        }
        for (i = 0; i < 4; i++) {
            s16* xy = (s16*)((u8*)p + 0x08 + i * 0x0C);
            xy[0] += dx - g_Tilemap.scrollX.i.hi;
            xy[1] += dy - g_Tilemap.scrollY.i.hi;
        }
        p->p3 = FAM_MARK;
        p = p->next;
        n++;
    }
    for (; p; p = p->next) { // the rest of the pool: kept, hidden
        p->type = PRIM_GT4;
        p->drawMode = DRAW_HIDE;
        p->p3 = FAM_MARK;
    }
    if (n) {
        for (i = 0; i < MAX_PRIM_COUNT; i++) {
            s_Shown[i] = !(g_PrimBuf[i].drawMode & DRAW_HIDE);
            g_PrimBuf[i].drawMode |= DRAW_HIDE;
        }
        for (k = 0, p = &g_PrimBuf[s_Pool]; k < n; k++, p = p->next) {
            if (s_Shown[p - g_PrimBuf]) {
                p->drawMode &= ~DRAW_HIDE;
            }
        }
        RenderPrimitives();
        PartnerBankPolys(gt4, gt3);
        for (i = 0; i < MAX_PRIM_COUNT; i++) {
            if (s_Shown[i]) {
                g_PrimBuf[i].drawMode &= ~DRAW_HIDE;
            }
        }
    }
    for (k = 0, p = &g_PrimBuf[s_Pool]; p && k < FAM_PRIMS; k++, p = p->next) {
        p->drawMode |= DRAW_HIDE; // not in the game's pass
    }
    return n;
}

// In the partner's drawing pass (partner.c, its slots in): its familiar's sprites, by themselves,
// moved with the body (dx, dy: the body's spot minus the partner's real one).
void FamiliarDraw(s16 dx, s16 dy) {
    static u16 s_Frames[256];
    static u8 s_Placed[COOP_SPRITES];
    const CoopSprite* s;
    Entity* e;
    u32* banks;
    u32 saved, gt4 = g_GpuUsage.gt4, gt3 = g_GpuUsage.gt3;
    s32 i, k, n = 0, slot = 63;

    g_CoopFamiliarDrawn = 0;
    if (!Ready()) {
        return;
    }
    for (i = 0; i < 256; i++) {
        s_Frames[i] = g_Entities[i].animCurFrame;
        g_Entities[i].animCurFrame = 0;
    }
    for (k = 0; k < g_CoopLink.partnerSpriteCount && k < COOP_SPRITES; k++) {
        s = &g_CoopLink.partnerSprites[k];
        s_Placed[k] = 0;
        if ((u16)s->animSet != ANIMSET_OVL(FAM_BANK) || s->weapon) {
            continue;
        }
        while (slot >= 4 && g_Entities[slot].entityId) {
            slot--;
        }
        if (slot < 4) {
            break;
        }
        e = &g_Entities[slot];
        for (i = 0; i < (s32)(sizeof(Entity) / 4); i++) {
            ((u32*)e)[i] = 0;
        }
        e->entityId = 0x7F; // never updated: only drawn
        e->animSet = s->animSet;
        e->animCurFrame = s->animCurFrame;
        e->posX.i.hi = s->x - g_Tilemap.scrollX.i.hi + dx;
        e->posY.i.hi = s->y - g_Tilemap.scrollY.i.hi + dy;
        e->palette = s->palette;
        e->facingLeft = s->facingLeft;
        e->blendMode = s->blendMode;
        e->zPriority = s->zPriority;
        e->drawFlags = s->drawFlags;
        e->unk5A = s->unk5A;
        s_Placed[k] = slot--;
        n++;
    }
    if (g_GameStep != Play_Default) {
        s_Pool = -1; // a load frees every primitive
    } else {
        g_CoopFamiliarDrawn = DrawPrims(dx, dy);
    }
    if (n) {
        banks = (u32*)g_api.o.spriteBanks;
        saved = banks[FAM_BANK];
        banks[FAM_BANK] = (u32)s_Table;
        RenderEntities();
        banks[FAM_BANK] = saved;
        PartnerBankPolys(gt4, gt3);
    }
    for (k = 0; k < COOP_SPRITES; k++) {
        if (s_Placed[k]) {
            e = &g_Entities[s_Placed[k]];
            for (i = 0; i < (s32)(sizeof(Entity) / 4); i++) {
                ((u32*)e)[i] = 0;
            }
            s_Placed[k] = 0;
        }
    }
    for (i = 0; i < 256; i++) {
        g_Entities[i].animCurFrame = s_Frames[i];
    }
    g_CoopFamiliarDrawn += n;
}
