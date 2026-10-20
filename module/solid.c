// Solid entities for a shared room's guest (D52: platforms and blocks didn't hold the guest up).
//
// An entity is solid because its own update calls the stage's GetPlayerCollisionWith(self, w,
// h, flags) every frame, which pushes the player out (src/st/st_common.h). The guest doesn't
// run those updates. So every overlay's GetPlayerCollisionWith jumps here instead (a copy of
// it); on a room's authority the calls are recorded and sent with the snapshot, and the guest
// makes the same calls against its copies, for its own player. Standing on one that moved
// sideways carries the guest along, as the platforms do for their own player.
#define COOP_MODULE
#include <game.h>
#include "solid.h"

#define STAGE_SLOTS (TOTAL_ENTITY_COUNT - STAGE_ENTITY_START)
#define ON_TOP 4

static SolidCall s_Calls[SOLID_CALLS_MAX];
static s32 s_NCalls;
static bool s_Record;
static s16 s_LastX[STAGE_SLOTS];  // guest: where each solid copy was (world x)...
static u16 s_LastAt[STAGE_SLOTS]; // ...and when
static u16 s_Frame;

// The stage's own, for the US build outside the prologue (src/st/st_common.h)
static u8 Collide(Entity* self, u16 w, u16 h, u16 flags) {
    Entity* player = &PLAYER;
    s16 x, y;
    u16 checks;
    s32 plStatus = g_Player.status;
    Collider col;

    x = self->posX.i.hi;
    y = self->posY.i.hi;
    if (x > 0x120 || x < -0x20 || y < -0x180 || y > 0x180) {
        return 0;
    }
    x = player->posX.i.hi - x;
    y = player->posY.i.hi - y;
    if (self->facingLeft) {
        x += self->hitboxOffX;
    } else {
        x -= self->hitboxOffX;
    }
    y -= self->hitboxOffY;
    g_api.GetPlayerSensor(&col);
    w += col.unk14;
    h += col.unk18;
    checks = x > 0 ? 1 : 0;
    if (y > 0) {
        checks |= 2;
    }
    x += w;
    y += h;
    w += w;
    h += h;
    if ((u16)x <= w && (u16)y <= h) {
        if (x && x != w) {
            if (flags & 4 && checks ^ 2 && player->velocityY >= 0 && y < 8) { // from the top
                player->posY.i.hi -= y;
                g_unkGraphicsStruct.shoveY.i.hi -= y;
                g_Player.vram_flag |= VRAM_FLAG_UNK40 | TOUCHING_GROUND;
                if (plStatus & (PLAYER_STATUS_BAT_FORM | PLAYER_STATUS_MIST_FORM)) {
                    return 0;
                }
                return 4;
            }
            if (flags & 2 && checks & 2 && (player->velocityY <= 0 || flags & 0x10)) { // below
                y = (s16)h - y;
                if (y < 0x10) {
                    player->posY.i.hi += y;
                    g_unkGraphicsStruct.shoveY.i.hi += y;
                    g_Player.vram_flag |= VRAM_FLAG_UNK40 | TOUCHING_CEILING;
                    if (plStatus & (PLAYER_STATUS_BAT_FORM | PLAYER_STATUS_MIST_FORM)) {
                        return 0;
                    }
                    return 2;
                }
            }
        }
        if (y && y != h && flags & 1) { // the sides
            if (checks & 1) {
                x = (s16)w - x;
                if (flags & 8 && x > 2) {
                    x = 2;
                }
                player->posX.i.hi += x;
                g_unkGraphicsStruct.shoveX.i.hi += x;
                g_Player.vram_flag |= VRAM_FLAG_UNK40 | TOUCHING_L_WALL;
            } else {
                if (flags & 8 && x > 2) {
                    x = 2;
                }
                player->posX.i.hi -= x;
                g_unkGraphicsStruct.shoveX.i.hi -= x;
                g_Player.vram_flag |= VRAM_FLAG_UNK40 | TOUCHING_R_WALL;
            }
            return 1;
        }
    }
    return 0;
}

// Every overlay's GetPlayerCollisionWith jumps here.
u8 CoopPlayerCollision(Entity* self, u16 w, u16 h, u16 flags) {
    s32 slot = self - &g_Entities[STAGE_ENTITY_START];

    if (s_Record && slot >= 0 && slot < STAGE_SLOTS && s_NCalls < SOLID_CALLS_MAX) {
        s_Calls[s_NCalls].slot = slot;
        s_Calls[s_NCalls].flags = flags;
        s_Calls[s_NCalls].w = w;
        s_Calls[s_NCalls].h = h;
        s_NCalls++;
    }
    return Collide(self, w, h, flags);
}

void SolidRecord(bool on) {
    s_Record = on;
    if (!on) {
        s_NCalls = 0;
    }
}

s32 SolidTake(SolidCall* out, s32 room) {
    s32 n = s_NCalls <= room ? s_NCalls : room;
    s32 i;

    for (i = 0; i < n; i++) {
        out[i] = s_Calls[i];
    }
    s_NCalls = 0;
    return n;
}

void SolidApply(const SolidCall* calls, s32 n, const u8* mirrored) {
    s32 i, slot, wx, dx;
    Entity* e;

    s_Frame++;
    for (i = 0; i < n; i++) {
        slot = calls[i].slot;
        e = &g_Entities[STAGE_ENTITY_START + slot];
        if (slot >= STAGE_SLOTS || !mirrored[slot] || !e->entityId) {
            continue;
        }
        wx = e->posX.i.hi + g_Tilemap.scrollX.i.hi;
        if (Collide(e, calls[i].w, calls[i].h, calls[i].flags) == ON_TOP &&
            s_LastAt[slot] == (u16)(s_Frame - 1)) {
            dx = wx - s_LastX[slot]; // ride along, as the platforms move their own player
            if (dx > -16 && dx < 16) {
                PLAYER.posX.i.hi += dx;
                g_unkGraphicsStruct.shoveX.i.hi += dx;
            }
        }
        s_LastX[slot] = wx;
        s_LastAt[slot] = s_Frame;
    }
}
