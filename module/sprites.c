// This player's own entities' sprites and primitives (subweapons, spells, the familiar, the hand
// weapons' swings...), sent with presence (design/M12). Since M13 the partner's body draws its own
// attacks in the partner's game (partner.c); what this sends is for what the body can't run there:
// a hand weapon that isn't the other game's (weapons.c) and the familiar (familiar.c).
#define COOP_MODULE
#include <game.h>
#include "link.h"
#include "sprites.h"
#include "weapons.h"

#define SLOT_FIRST 4
#define SLOT_LAST 63

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
        s->weapon = 0;
        WeaponSprite(e, s); // a hand weapon's: as the partner draws it
    }
    g_CoopLink.selfSpriteCount = n;
}


// --- its primitives ----------------------------------------------------------------------------
// Copied with positions in the room (all four vertices; a tile's w,h are in u0,v0 and stay).
#define DRAW_HIDDEN 8 // DRAW_HIDE

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
            // M13 step 4: a familiar's (the sword's are primitives), for the partner's body to keep
            g_CoopLink.selfPrims[n][PRIM_TAG] = e->entityId >= FAMILIAR_IDS && e->entityId < FAMILIAR_IDS + 0x10 ? FAMILIAR_TAG : 0;
            n++;
        }
    }
    g_CoopLink.selfPrimCount = n;
}

