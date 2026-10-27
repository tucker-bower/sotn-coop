// The partner's attacks on this screen (playtest 2026-10-25 note 2, design/M12): the sprites of
// the partner's own entities (subweapons, spells, the familiar, Richter's whip effects...) are sent
// with presence, and drawn here by the game itself: just before RenderEntities they're put in free
// player entity slots as inert entities (never updated, never hit), and taken out right after.
// Phase 1: sprites whose graphics this game has too: DRA's sprite sets (Alucard's subweapons and
// spell effects), and the overlay's own sets when the partner plays this game's character. Hand
// weapons (their sheets are only in the partner's VRAM) are phase 2 (D106).
#define COOP_MODULE
#include <game.h>
#include "link.h"
#include "character.h"
#include "sprites.h"

#define SLOT_FIRST 4
#define SLOT_LAST 63
#define OVL_BANK(set) ((set) & 0x7FFF)

static u8 s_Placed[COOP_SPRITES]; // the slots this frame's partner sprites went in (0: none)
u32 g_CoopSpritesDrawn; // how many went in last frame (tests read it: coop.map)
u32 g_CoopSpritesWhy;   // why none: 1 not in play, 2 partner not here, 3 none drawable

// Their sets: drawable here? DRA's, yes; an overlay's only from the same character, and never the
// weapon banks (0x10-0x13 hold this player's hand weapons in Alucard's game; 0x17 its off-hand).
static bool Drawable(const CoopSprite* s) {
    s32 bank;

    if (!(s->animSet & ANIMSET_OVL_FLAG)) {
        return s->animSet > 0;
    }
    bank = OVL_BANK(s->animSet);
    if (g_CoopLink.partner.character != CharacterLoaded() || bank == 0x17) {
        return false;
    }
    return !(CharacterLoaded() == CHAR_ALUCARD && bank >= 0x10 && bank < 0x14);
}

// This game's: after RenderEntities, with presence.
void SpritesCapture(void) {
    s32 i, n = 0;
    Entity* e;
    CoopSprite* s;

    for (i = SLOT_FIRST; i <= SLOT_LAST && n < COOP_SPRITES; i++) {
        e = &g_Entities[i];
        if (!e->entityId || !e->animSet || !(e->animCurFrame & 0x7FFF)) {
            continue;
        }
        s = &g_CoopLink.selfSprites[n++];
        s->animSet = e->animSet;
        s->animCurFrame = e->animCurFrame;
        s->x = e->posX.i.hi + g_Tilemap.scrollX.i.hi;
        s->y = e->posY.i.hi + g_Tilemap.scrollY.i.hi;
        s->palette = e->palette;
        s->facingLeft = e->facingLeft;
        s->blendMode = e->blendMode;
        s->zPriority = e->zPriority;
        s->drawFlags = e->drawFlags;
        s->unk5A = e->unk5A;
    }
    g_CoopLink.selfSpriteCount = n;
}

static bool PartnerHere(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    return g_CoopLink.partnerAge <= 30 && (p->flags & PRESENCE_IN_PLAY) && SAME_WORLD(p) &&
           p->stage == g_StageId && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top;
}

// Before RenderEntities: the partner's sprites into free slots.
void SpritesPlace(void) {
    s32 i, k, slot = SLOT_LAST;
    const CoopSprite* s;
    Entity* e;

    for (k = 0; k < COOP_SPRITES; k++) {
        s_Placed[k] = 0;
    }
    g_CoopSpritesDrawn = 0;
    if (g_GameState != Game_Play || !PartnerHere()) {
        g_CoopSpritesWhy = g_GameState != Game_Play ? 1 : 2;
        return;
    }
    g_CoopSpritesWhy = 3;
    for (k = 0; k < g_CoopLink.partnerSpriteCount && k < COOP_SPRITES; k++) {
        s = &g_CoopLink.partnerSprites[k];
        if (!Drawable(s)) {
            continue;
        }
        while (slot >= SLOT_FIRST && g_Entities[slot].entityId) {
            slot--;
        }
        if (slot < SLOT_FIRST) {
            return;
        }
        e = &g_Entities[slot];
        for (i = 0; i < (s32)(sizeof(Entity) / 4); i++) {
            ((u32*)e)[i] = 0;
        }
        e->entityId = 0x7F; // nonzero, so nothing else takes the slot meanwhile; never updated
        e->animSet = s->animSet;
        e->animCurFrame = s->animCurFrame;
        e->posX.i.hi = s->x - g_Tilemap.scrollX.i.hi;
        e->posY.i.hi = s->y - g_Tilemap.scrollY.i.hi;
        e->palette = s->palette;
        e->facingLeft = s->facingLeft;
        e->blendMode = s->blendMode;
        e->zPriority = s->zPriority;
        e->drawFlags = s->drawFlags;
        e->unk5A = s->unk5A;
        s_Placed[k] = slot--;
        g_CoopSpritesDrawn++;
        g_CoopSpritesWhy = 0;
    }
}

// After RenderEntities: out again.
void SpritesRemove(void) {
    s32 i, k;
    Entity* e;

    for (k = 0; k < COOP_SPRITES; k++) {
        if (s_Placed[k]) {
            e = &g_Entities[s_Placed[k]];
            for (i = 0; i < (s32)(sizeof(Entity) / 4); i++) {
                ((u32*)e)[i] = 0;
            }
            s_Placed[k] = 0;
        }
    }
}

// --- their primitives -------------------------------------------------------------------------
// Copied with positions in the room (all four vertices; a tile's w,h are in u0,v0 and stay), and
// replayed in a pool of this game's own primitives, allocated once per stage (a stage load frees
// them all), hidden when unused: the game draws them itself.
#define PRIM_XY(p, k) ((s16*)((u8*)(p) + 0x08 + (k) * 0x0C)) // x0,y0 / x1,y1 / x2,y2 / x3,y3
#define DRAW_HIDDEN 8 // DRAW_HIDE
// Our pool's mark, in each primitive's p3 (the GPU packet's pad byte: rendering ignores it). The
// game frees every primitive at a stage load and in some menus (DestroyAllPrimitives zeroes them):
// a pool without its mark is gone, and its slots may be someone else's now.
#define POOL_MARK 0xC5
static s16 s_Pool = -1;

static bool PoolIntact(void) {
    s32 k;
    Primitive* p;

    if (s_Pool < 0) {
        return false;
    }
    for (k = 0, p = &g_PrimBuf[s_Pool]; k < COOP_PRIMS; k++, p = p->next) {
        if (!p || p->type == PRIM_NONE || p->p3 != POOL_MARK) {
            return false;
        }
    }
    return true;
}

static void Shift(u8* data, s32 dx, s32 dy) { // data: a Primitive's bytes from 0x04
    s32 k;
    for (k = 0; k < 4; k++) {
        s16* xy = (s16*)(data - 4 + 0x08 + k * 0x0C);
        xy[0] += dx;
        xy[1] += dy;
    }
}

void PrimsCapture(void) {
    s32 i, n = 0;
    Entity* e;
    Primitive* p;

    for (i = 1; i < SLOT_LAST + 1 && n < COOP_PRIMS; i++) {
        e = &g_Entities[i];
        if (!e->entityId || !(e->flags & FLAG_HAS_PRIMS) || e->primIndex < 0 || e->primIndex >= MAX_PRIM_COUNT) {
            continue;
        }
        for (p = &g_PrimBuf[e->primIndex]; p && n < COOP_PRIMS; p = p->next) {
            if ((p->drawMode & DRAW_HIDDEN) || p->type == PRIM_NONE) {
                continue;
            }
            __builtin_memcpy(g_CoopLink.selfPrims[n], (u8*)p + 4, COOP_PRIM_SIZE);
            Shift(g_CoopLink.selfPrims[n], g_Tilemap.scrollX.i.hi, g_Tilemap.scrollY.i.hi);
            n++;
        }
    }
    g_CoopLink.selfPrimCount = n;
}

void PrimsPlace(void) {
    s32 k;
    Primitive* p;
    bool here = g_GameState == Game_Play && PartnerHere();

    if (g_GameState != Game_Play || g_GameStep != Play_Default) {
        s_Pool = -1; // a load frees every primitive
        return;
    }
    if (!PoolIntact()) {
        s_Pool = g_api.AllocPrimitives(PRIM_GT4, COOP_PRIMS);
        if (s_Pool < 0) {
            return;
        }
    }
    for (k = 0, p = &g_PrimBuf[s_Pool]; p && k < COOP_PRIMS; k++, p = p->next) {
        if (here && k < (s32)g_CoopLink.partnerPrimCount && g_CoopLink.partnerPrims[k][3] != PRIM_NONE) {
            Primitive* next = p->next;
            __builtin_memcpy((u8*)p + 4, g_CoopLink.partnerPrims[k], COOP_PRIM_SIZE);
            p->next = next;
            Shift((u8*)p + 4, -g_Tilemap.scrollX.i.hi, -g_Tilemap.scrollY.i.hi);
        } else {
            p->type = PRIM_GT4; // keep the pool's (never PRIM_NONE: that frees it)
            p->drawMode = DRAW_HIDDEN;
        }
        p->p3 = POOL_MARK;
    }
}
