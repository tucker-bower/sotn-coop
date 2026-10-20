// Shared rooms: the same enemies for both players (design/M4-shared-rooms.md).
//
// When both players are in the same room with their cameras close, the player who entered first
// is the room's AUTHORITY: its game runs the room as normal and, after each update, writes a
// snapshot of the room (stage entities, the primitives they draw with, the stage overlay's BSS).
// The other game is the GUEST: its own stage update and layout spawner are switched off, and
// before each update it copies the latest snapshot in, shifted to its own camera. It still runs
// its own player and hit detection: enemies hurt the guest natively, and what the guest's
// attacks did to the copies goes back to the authority as hit events.
//
// The enemy targeting helpers of every stage are patched to aim at the nearer player.
#define COOP_MODULE
#include <game.h>
#include "link.h"
#include "overlay_table.h"
#include "boss.h"
#include "progress.h"
#include "shared.h"
#include "solid.h"
#include "vram.h"

s32 AllocPrimitives(u8 type, s32 count); // DRA
void FreePrimitives(s32 index);          // DRA
void DestroyEntity(Entity* entity);      // DRA
void FlushCache(void);                   // main.exe

#define STAGE_SLOTS (TOTAL_ENTITY_COUNT - STAGE_ENTITY_START)
#define ABS(x) ((x) < 0 ? -(x) : (x))
#define ROLE_SETTLE 4      // frames a role change must hold before it happens
#define MAX_PRIMS_PER_ENTITY 64
#define CAMERA_NEAR 256    // shared only while the cameras are within a screen of each other
#define UI_PRIORITY 0x1E0  // primitives from here up are screen-space UI (message boxes, 0x1FC+)

typedef struct {
    u16 stage;
    s16 roomLeft, roomTop;
    s16 scrollX, scrollY;
    u16 nEntities;
    u16 bssSize;
    u16 nSolid; // GetPlayerCollisionWith calls follow the VRAM uploads (solid.c)
    u32 killed[8]; // g_unkGraphicsStruct.D_80097428: the room's layout entities already killed
    u16 fgTiles;   // the room's foreground tile layer follows (after the BSS), or 0: unchanged
    u16 vramBytes; // then the stage's VRAM uploads this frame (vram.c)
} SnapHeader;

// The room's foreground tiles: doors, breakable walls and the like change them (and so what's
// solid). The guest doesn't run those, so it gets the authority's tiles: a door closed in the
// authority's world is closed for the guest too (M5: the guest walked out of a boss room).
#define FG_RESEND 60 // frames: also send the unchanged layer this often
#define FG_MAX 0x2000 // tiles; bigger rooms aren't sent
static u32 s_FgSum;
static u16 s_FgAge;

static s32 FgTiles(void) {
    s32 n = g_Tilemap.hSize * 16 * g_Tilemap.vSize * 16;
    return g_Tilemap.fg && n > 0 && n <= FG_MAX ? n : 0;
}

static u32 FgSum(s32 n) {
    const u32* w = (const u32*)g_Tilemap.fg;
    u32 sum = 0;
    s32 i;

    for (i = 0; i < n / 2; i++) {
        sum = (sum << 1 | sum >> 31) ^ w[i];
    }
    return sum;
}

typedef struct {
    u8 slot;   // 0..191 (+ STAGE_ENTITY_START)
    u8 nPrims; // primitives that follow the entity
    u16 nEnvs; // then the DR_ENV of each PRIM_ENV among them, in order
} SnapEntity;

// A PRIM_ENV primitive (a render-to-texture pass: the Warg burning away) points at a DR_ENV from
// DRA's pool, through prim->r1. The guest can't use the authority's pointer: the same address is
// one of its own pool entries, maybe in use (Alucard's afterimages). Each mirrored PRIM_ENV gets
// a pool entry of the guest's own, holding the authority's contents.
DR_ENV* func_800EDB08(Primitive* prim); // DRA: allocates a DR_ENV for prim, sets it up as PRIM_ENV
#define PRIM_ENV_PTR(p) (*(DR_ENV**)&(p)->r1)

static s32 s_Role, s_Want, s_Settle;
static u16 s_RoomFrames;
static s16 s_RoomLeft, s_RoomTop;
static s32 s_RoomStage = -1;

// Guest: what it switched off, and the primitives it allocated for copies.
static void (*s_OrigUpdate)(void);
static void (*s_OrigSpawner)(void);
static s16 s_MirrorPrims[STAGE_SLOTS]; // head index per slot, -1 if none
static u8 s_MirrorCount[STAGE_SLOTS];  // primitives in that chain (kept while the count holds)
static u8 s_Mirrored[STAGE_SLOTS];     // the slot holds a copy (not a local entity)
static u8 s_Local[STAGE_SLOTS];        // the slot holds scenery the guest runs itself
static u8 s_TakenHere[STAGE_SLOTS];    // frames to keep not copying a drop this game took
#define TAKEN_FRAMES 30
#define E_PRIZE_DROP 3 // hearts, gold, subweapons: the same entity id in every stage
static u32 s_AppliedSeq;

// Hit detection wrapper, and hits the guest made (authority applies them)
static void (*s_HitDetection)(void);
typedef struct {
    u8 slot;
    u16 entityId;
    s16 damage;
    u8 hitFlags, dead, invincibility, stun;
    u8 hitParams; // what breakables (candles) react to: the attack's hit effect
    u16 hitEffect;
    bool second; // the EV_HIT2 half arrived
} PendingHit;
static PendingHit s_Hits[32];
static s32 s_NHits;

// Entities the guest's hit detection created, to create in the authority's world
typedef struct {
    u16 entityId;
    u16 params;
    u32 pfnUpdate;
    s16 x, y; // world
    u8 range; // 0: slots 160-191, 1: 224-255
    u8 parts; // events received (3 = complete)
    s32 velocityY;
    u16 stage; // when it arrived: pfnUpdate points into that stage's overlay
    s32 castleFlag;
} PendingSpawn;
static PendingSpawn s_Spawns[16];
static s32 s_NSpawns;
#define SPAWN_FIRST 160 // hit detection creates its entities in 160-191 and 224-255
#define SPAWN_SECOND 224

// Targeting patch: which overlay was patched last
static void* s_PatchedFor;

static void Stub(void) {}

// The authority's GetPlayerCollisionWith calls from its last snapshot: the guest makes them too
static const SolidCall* s_Solid;
static s32 s_NSolid;

// The guest's stage update: only the scenery it runs itself (see IsScenery). Everything else
// in the room is a copy of the authority's.
static void GuestUpdate(void) {
    Entity* e;
    s32 i;

    // The stage update's own bookkeeping: the bottom corner text (an item's name when the
    // guest picks it up) goes away when its timer runs out.
    if (g_unkGraphicsStruct.BottomCornerTextTimer) {
        if (!--g_unkGraphicsStruct.BottomCornerTextTimer) {
            FreePrimitives(g_unkGraphicsStruct.BottomCornerTextPrims);
        }
    }

    for (i = 0; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (s_Local[i] && e->pfnUpdate) {
            g_CurrentEntity = e;
            e->pfnUpdate(e);
        }
    }
    if (s_Solid) {
        SolidApply(s_Solid, s_NSolid, s_Mirrored);
    }
}

// Scenery that draws from the camera (3D projection, parallax: bushes, trees, clouds...): the
// authority's primitives are only right for the authority's camera, so the guest runs these
// itself (playtest 1: trees and bushes in the wrong place on the guest's screen).
static bool IsScenery(const OverlayInfo* ovl, u32 pfn) {
    const u32* d;

    if (!ovl) {
        return false;
    }
    for (d = ovl->decor; *d; d++) {
        if (*d == pfn) {
            return true;
        }
    }
    return false;
}

// Snapshots move kilobytes every frame: copy whole words (entities, primitives and snapshot
// records are all word-aligned), never bytes (D40).
static void CopyWords(void* dst, const void* src, s32 bytes) {
    u32* d = dst;
    const u32* s = src;
    s32 n = bytes >> 2;

    while (n >= 4) {
        d[0] = s[0];
        d[1] = s[1];
        d[2] = s[2];
        d[3] = s[3];
        d += 4;
        s += 4;
        n -= 4;
    }
    while (n--) {
        *d++ = *s++;
    }
}

// --- roles

static bool PartnerShareable(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    s32 dx, dy;

    if (g_CoopLink.partnerAge > 30 || !(p->flags & PRESENCE_IN_PLAY) ||
        (p->flags & (PRESENCE_BUSY | PRESENCE_DEAD)) || p->character != g_PlayableCharacter) {
        return false;
    }
    if (g_GameState != Game_Play || g_GameStep != Play_Default || g_GameEngineStep != Engine_Normal) {
        return false;
    }
    if (p->stage != g_StageId || p->roomLeft != g_Tilemap.left || p->roomTop != g_Tilemap.top) {
        return false;
    }
    dx = p->scrollX - g_Tilemap.scrollX.i.hi;
    dy = p->scrollY - g_Tilemap.scrollY.i.hi;
    return dx > -CAMERA_NEAR && dx < CAMERA_NEAR && dy > -CAMERA_NEAR && dy < CAMERA_NEAR;
}

static bool IAmAuthority(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    if (s_RoomFrames != p->roomFrames) {
        return s_RoomFrames > p->roomFrames; // whoever was here first
    }
    return g_CoopLink.rank < 1; // a tie: rank 0
}

static void BecomeGuest(void);
static void StopBeingGuest(void);

static void DecideRole(void) {
    s32 want;

    if (!PartnerShareable()) {
        want = ROLE_NONE;
    } else if (s_Role != ROLE_NONE) {
        want = s_Role; // roles stay put while the room is shared...
        if (g_CoopLink.partner.role == s_Role) {
            // ...unless both games picked the same one (they decided a frame apart): rank decides
            want = g_CoopLink.rank == 0 ? ROLE_AUTHORITY : ROLE_GUEST;
        }
    } else {
        want = IAmAuthority() ? ROLE_AUTHORITY : ROLE_GUEST;
    }
    if (want == s_Role) {
        s_Settle = 0;
        return;
    }
    if (want != s_Want) {
        s_Want = want;
        s_Settle = 0;
    }
    if (++s_Settle < ROLE_SETTLE) {
        return;
    }
    if (s_Role == ROLE_GUEST) {
        StopBeingGuest();
    }
    s_Role = want;
    if (s_Role == ROLE_GUEST) {
        BecomeGuest();
    }
    s_Settle = 0;
}

static void TrackRoom(void) {
    if (g_StageId != s_RoomStage || g_Tilemap.left != s_RoomLeft || g_Tilemap.top != s_RoomTop) {
        s_RoomStage = g_StageId;
        s_RoomLeft = g_Tilemap.left;
        s_RoomTop = g_Tilemap.top;
        s_RoomFrames = 0;
    } else if (s_RoomFrames < 0xFFFF) {
        s_RoomFrames++;
    }
}

// --- guest

static void BecomeGuest(void) {
    s32 i;

    for (i = 0; i < STAGE_SLOTS; i++) {
        s_MirrorPrims[i] = -1;
        s_MirrorCount[i] = 0;
        s_Mirrored[i] = false;
        s_Local[i] = false;
        s_TakenHere[i] = 0;
    }
    s_OrigUpdate = g_api.o.Update;
    s_OrigSpawner = g_api.o.UpdateRoomPosition;
    s_AppliedSeq = g_CoopLink.snapInSeq;
}

#define LAYOUT_START 0xFFFE
#define LAYOUT_END 0xFFFF
#define LAYOUT_ENTRY 5 // u16s per layout entry: x, y, entityId, slot | flag << 8, params

// The layout spawner's cursors came from the authority (they're in the BSS) and point where the
// authority's camera was. Left there, the spawner would sweep everything between that and this
// game's camera on its next scroll, and bring back enemies already killed. Re-seat them for this
// camera, as InitRoomEntities leaves them, without spawning anything.
static void ResyncSpawner(void) {
    const OverlayInfo* ovl = FindOverlay(g_StageId);
    u16** h;
    u16** v;
    s32 right, below;

    if (!ovl || !ovl->layout[LAYOUT_H] || !ovl->layout[LAYOUT_V]) {
        return;
    }
    h = (u16**)ovl->layout[LAYOUT_H];
    v = (u16**)ovl->layout[LAYOUT_V];
    if (!*h || !*v) {
        return;
    }
    right = g_Tilemap.scrollX.i.hi + 320;
    below = g_Tilemap.scrollY.i.hi + 288;
    while ((*h)[0] != LAYOUT_START) { // back to the head of the x-sorted list...
        *h -= LAYOUT_ENTRY;
    }
    *h += LAYOUT_ENTRY; // ...then past everything already in range
    while ((*h)[0] != LAYOUT_END && (*h)[0] <= right) {
        *h += LAYOUT_ENTRY;
    }
    while ((*v)[1] != LAYOUT_START) { // the y-sorted list, the same way
        *v -= LAYOUT_ENTRY;
    }
    while ((*v)[1] == LAYOUT_START || (*v)[1] < below) {
        *v += LAYOUT_ENTRY;
    }
    *(u8*)ovl->layout[LAYOUT_POS_H] = 0; // LAYOUT_OBJ_POSITION_FORWARD
    *(u8*)ovl->layout[LAYOUT_POS_V] = 0;
}

// The copies become this game's own world: their primitives are theirs now, and the stage
// logic runs them from here (that's the hand-over: design/M4, part 1).
static void StopBeingGuest(void) {
    ResyncSpawner();
    if (g_api.o.Update == GuestUpdate) {
        g_api.o.Update = s_OrigUpdate;
    }
    if (g_api.o.UpdateRoomPosition == Stub) {
        g_api.o.UpdateRoomPosition = s_OrigSpawner;
    }
}

static void KeepStubbed(void) {
    if (g_api.o.Update != GuestUpdate) { // a fresh overlay load rewrote the table
        s_OrigUpdate = g_api.o.Update;
        g_api.o.Update = GuestUpdate;
    }
    if (g_api.o.UpdateRoomPosition != Stub) {
        s_OrigSpawner = g_api.o.UpdateRoomPosition;
        g_api.o.UpdateRoomPosition = Stub;
    }
}

static void ShiftPrim(Primitive* p, s32 dx, s32 dy) {
    switch (p->type & 0xF) {
    case PRIM_G4:
    case PRIM_GT4:
        p->x3 += dx;
        p->y3 += dy;
    case PRIM_GT3:
        p->x2 += dx;
        p->y2 += dy;
    case PRIM_LINE_G2:
        p->x1 += dx;
        p->y1 += dy;
    case PRIM_TILE:
    case PRIM_SPRT:
        p->x0 += dx;
        p->y0 += dy;
    }
}

static void FreeMirrorPrims(s32 i) {
    if (s_MirrorPrims[i] >= 0) {
        FreePrimitives(s_MirrorPrims[i]);
        s_MirrorPrims[i] = -1;
        s_MirrorCount[i] = 0;
    }
}

static void ClearSlot(s32 i) {
    Entity* e = &g_Entities[STAGE_ENTITY_START + i];

    if (s_Mirrored[i]) {
        FreeMirrorPrims(i);
        e->flags &= ~FLAG_HAS_PRIMS;
        DestroyEntity(e);
        s_Mirrored[i] = false;
    } else if (e->entityId) {
        DestroyEntity(e); // something local (a hit spark): the snapshot decides what's here
    }
    s_Local[i] = false;
}

static void ApplySnapshot(void) {
    const u8* r = g_CoopLink.snapIn;
    const u8* end = g_CoopLink.snapIn + g_CoopLink.snapInSize;
    const SnapHeader* h = (const SnapHeader*)r;
    const OverlayInfo* ovl;
    u8 present[STAGE_SLOTS];
    s32 i, k, dx, dy, sx, sy, n, idx = -1;
    Entity* e;
    Primitive* p;
    Primitive* next;
    const DR_ENV* env;
    DR_ENV* mine;

    if (g_CoopLink.snapInSeq == s_AppliedSeq || g_CoopLink.snapInSize < sizeof(SnapHeader) ||
        h->stage != g_StageId || h->roomLeft != g_Tilemap.left || h->roomTop != g_Tilemap.top) {
        return; // nothing new, or not this room's
    }
    s_AppliedSeq = g_CoopLink.snapInSeq;
    // The layout spawner skips entities marked killed here; without it, a hand-over respawns
    // everything the authority killed (playtest 1: the wolves came back).
    for (i = 0; i < 8; i++) { // OR: the guest's own kills set bits here first
        g_unkGraphicsStruct.D_80097428[i] |= h->killed[i];
    }
    dx = h->scrollX - g_Tilemap.scrollX.i.hi;
    dy = h->scrollY - g_Tilemap.scrollY.i.hi;
    r += sizeof(SnapHeader);

    ovl = FindOverlay(g_StageId);
    for (i = 0; i < STAGE_SLOTS; i++) {
        present[i] = false;
        if (s_TakenHere[i]) {
            s_TakenHere[i]--;
        }
    }
    for (k = 0; k < h->nEntities && r + sizeof(SnapEntity) + sizeof(Entity) <= end; k++) {
        const SnapEntity* se = (const SnapEntity*)r;
        const Entity* se_e = (const Entity*)(r + sizeof(SnapEntity));
        const Primitive* src;

        r += sizeof(SnapEntity);
        i = se->slot;
        present[i] = true;
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (s_TakenHere[i] && se_e->entityId == E_PRIZE_DROP) { // a drop this game just took
            r += sizeof(Entity) + se->nPrims * sizeof(Primitive) + se->nEnvs * sizeof(DR_ENV);
            continue;
        }
        if (IsScenery(ovl, (u32)se_e->pfnUpdate)) {
            r += sizeof(Entity) + se->nPrims * sizeof(Primitive);
            if (!s_Mirrored[i] && e->entityId == se_e->entityId && e->pfnUpdate == se_e->pfnUpdate) {
                s_Local[i] = true; // already running here (this game spawned it too): keep it
                continue;
            }
            ClearSlot(i);
            CopyWords(e, se_e, sizeof(Entity)); // a fresh one: it sets itself up on its first update
            e->flags &= ~FLAG_HAS_PRIMS;
            e->primIndex = 0;
            e->step = 0;
            if (e->unk68) {
                e->posX.val += dx * e->unk68 * 0x100;
                e->posY.val += dy * e->unk68 * 0x100;
            } else if (e->flags & FLAG_POS_CAMERA_LOCKED) {
                e->posX.i.hi += dx;
                e->posY.i.hi += dy;
            }
            s_Local[i] = true;
            continue;
        }
        if (!s_Mirrored[i] && e->entityId) {
            DestroyEntity(e);
        }
        s_Local[i] = false;
        CopyWords(e, r, sizeof(Entity));
        r += sizeof(Entity);
        s_Mirrored[i] = true;
        src = (const Primitive*)r;
        n = se->nPrims;
        r += n * sizeof(Primitive);
        env = (const DR_ENV*)r;
        r += se->nEnvs * sizeof(DR_ENV);
        e->flags &= ~FLAG_HAS_PRIMS;
        if (n != s_MirrorCount[i]) { // keep last frame's chain if it's the right length
            FreeMirrorPrims(i);
            // Never allocate as PRIM_ENV: a fresh one has no DR_ENV, and freeing it would write
            // through a null pointer. The copy below sets each primitive's real type.
            if (n && (idx = AllocPrimitives(PRIM_GT4, n)) >= 0) {
                s_MirrorPrims[i] = idx;
                s_MirrorCount[i] = n;
            }
        }
        // Same rule as the engine's own per-frame camera shift: world-anchored entities move
        // by the camera difference, parallax ones (unk68) by a fraction of it. Their primitives
        // move the same way: on the guest nothing recomputes them from the entity (playtest 1:
        // background trees followed the authority's camera).
        sx = sy = 0;
        if (e->unk68) {
            e->posX.val += dx * e->unk68 * 0x100;
            e->posY.val += dy * e->unk68 * 0x100;
            sx = (dx * e->unk68) >> 8;
            sy = (dy * e->unk68) >> 8;
        } else if (e->flags & FLAG_POS_CAMERA_LOCKED) {
            e->posX.i.hi += dx;
            e->posY.i.hi += dy;
            sx = dx;
            sy = dy;
        }
        if (n && s_MirrorPrims[i] >= 0 && r <= end) {
            for (p = &g_PrimBuf[s_MirrorPrims[i]]; p && n--; p = next, src++) {
                next = p->next;
                mine = p->type == PRIM_ENV ? PRIM_ENV_PTR(p) : NULL; // this mirror's own DR_ENV
                CopyWords(p, src, sizeof(Primitive));
                p->next = next;
                if (p->type == PRIM_ENV) {
                    if (!mine) {
                        mine = func_800EDB08(p); // the pool's next free entry (sets r1)
                    }
                    if (mine && PRIM_ENV_PTR(src) && (u8*)(env + 1) <= end) {
                        CopyWords(mine, env++, sizeof(DR_ENV));
                    }
                    if (mine) {
                        PRIM_ENV_PTR(p) = mine;
                    } else { // the pool is full: don't draw it (and never free a foreign entry)
                        p->type = PRIM_NONE;
                        p->drawMode = DRAW_HIDE;
                    }
                } else if (mine) {
                    *(u32*)mine = 0; // released, as FreePrimitives does
                }
                // On-screen UI an entity draws (a relic's "Obtained ..." box) stays where it is.
                if ((sx || sy) && p->priority < UI_PRIORITY && !(p->drawMode & DRAW_ABSPOS)) {
                    ShiftPrim(p, sx, sy);
                }
            }
            e->primIndex = s_MirrorPrims[i];
            e->flags |= FLAG_HAS_PRIMS;
        }
    }
    for (i = 0; i < STAGE_SLOTS; i++) {
        if (!present[i]) {
            ClearSlot(i);
        }
    }
    if (ovl && h->bssSize == ovl->bssSize && r + h->bssSize <= end) {
        CopyWords((void*)ovl->bssStart, r, h->bssSize);
    }
    r += h->bssSize;
    if (h->fgTiles && h->fgTiles == FgTiles() && r + h->fgTiles * 2 <= end) {
        CopyWords(g_Tilemap.fg, r, h->fgTiles * 2);
    }
    r += h->fgTiles * 2;
    if (h->vramBytes && r + h->vramBytes <= end) {
        VramApply(r, h->vramBytes);
    }
    r += h->vramBytes;
    s_Solid = NULL;
    if (r + h->nSolid * sizeof(SolidCall) <= end) {
        s_Solid = (const SolidCall*)r;
        s_NSolid = h->nSolid;
    }
}

// --- authority

static void CaptureSnapshot(void) {
    u8* w = g_CoopLink.snapOut;
    u8* end = g_CoopLink.snapOut + SNAP_MAX;
    SnapHeader* h = (SnapHeader*)w;
    const OverlayInfo* ovl = FindOverlay(g_StageId);
    s32 i, n, k, envs;
    Entity* e;
    Primitive* p;

    h->stage = g_StageId;
    h->roomLeft = g_Tilemap.left;
    h->roomTop = g_Tilemap.top;
    h->scrollX = g_Tilemap.scrollX.i.hi;
    h->scrollY = g_Tilemap.scrollY.i.hi;
    h->nEntities = 0;
    h->bssSize = 0;
    for (i = 0; i < 8; i++) {
        h->killed[i] = g_unkGraphicsStruct.D_80097428[i];
    }
    w += sizeof(SnapHeader);
    for (i = 0; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (!e->entityId) {
            continue;
        }
        n = 0;
        if (e->flags & FLAG_HAS_PRIMS) {
            for (p = &g_PrimBuf[e->primIndex]; p && n < MAX_PRIMS_PER_ENTITY; p = p->next) {
                n++;
            }
        }
        if (w + sizeof(SnapEntity) + sizeof(Entity) + n * sizeof(Primitive) > end) {
            break; // out of room: the rest stay as they were last time on the guest
        }
        envs = 0;
        k = 0;
        for (p = n ? &g_PrimBuf[e->primIndex] : NULL; p && k < n; p = p->next, k++) {
            envs += p->type == PRIM_ENV && PRIM_ENV_PTR(p);
        }
        if (w + sizeof(SnapEntity) + sizeof(Entity) + n * sizeof(Primitive) + envs * sizeof(DR_ENV) > end) {
            break;
        }
        ((SnapEntity*)w)->slot = i;
        ((SnapEntity*)w)->nPrims = n;
        ((SnapEntity*)w)->nEnvs = envs;
        w += sizeof(SnapEntity);
        CopyWords(w, e, sizeof(Entity));
        ((Entity*)w)->pfnUpdate = BossRealUpdate(e); // not the aggro wrapper (module state)
        w += sizeof(Entity);
        for (p = n ? &g_PrimBuf[e->primIndex] : NULL; p && n--; p = p->next) {
            CopyWords(w, p, sizeof(Primitive));
            w += sizeof(Primitive);
        }
        for (p = envs ? &g_PrimBuf[e->primIndex] : NULL; p && envs; p = p->next) {
            if (p->type == PRIM_ENV && PRIM_ENV_PTR(p)) {
                CopyWords(w, PRIM_ENV_PTR(p), sizeof(DR_ENV));
                w += sizeof(DR_ENV);
                envs--;
            }
        }
        h->nEntities++;
    }
    if (ovl && w + ovl->bssSize <= end) {
        CopyWords(w, (void*)ovl->bssStart, ovl->bssSize);
        w += ovl->bssSize;
        h->bssSize = ovl->bssSize;
    }
    h->fgTiles = 0;
    n = FgTiles();
    if (n && (n & 1) == 0 && h->bssSize == (ovl ? ovl->bssSize : 0)) {
        u32 sum = FgSum(n);
        if ((sum != s_FgSum || ++s_FgAge >= FG_RESEND) && w + n * 2 <= end) {
            CopyWords(w, g_Tilemap.fg, n * 2);
            w += n * 2;
            h->fgTiles = n;
            s_FgSum = sum;
            s_FgAge = 0;
        }
    }
    h->vramBytes = VramTake(w, end - w);
    w += h->vramBytes;
    h->nSolid = SolidTake((SolidCall*)w, (end - w) / sizeof(SolidCall));
    w += h->nSolid * sizeof(SolidCall);
    g_CoopLink.snapOutSize = w - g_CoopLink.snapOut;
    g_CoopLink.snapOutSeq++;
}

// --- hits

// A prize drop (hearts, gold, a subweapon: entity 3 in every stage, src/st/e_collect.h) the
// guest touches is the guest's: its own copy collects it right away (the drop's update does,
// in the frame it's touched), and the authority removes the real one, rewarding nobody. Before,
// the authority's player got the hearts, or the subweapon (D51).
static u8 s_Taken[16];
static u16 s_TakenId[16];
static s32 s_NTaken;


static void CollectTouchedDrops(void) {
    s32 i;
    Entity* e;

    for (i = 0; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (!s_Mirrored[i] || e->entityId != E_PRIZE_DROP || !e->hitFlags || !e->pfnUpdate ||
            e->step < 2 || e->step >= 5) {
            continue;
        }
        ProgressEmit(EV_TAKEN, i | (e->entityId << 8), 0);
        FreeMirrorPrims(i); // the copy's primitives are the mirror's: free them here, once
        e->flags &= ~FLAG_HAS_PRIMS;
        s_TakenHere[i] = TAKEN_FRAMES; // the real one lasts until the authority hears
        g_CurrentEntity = e;
        e->pfnUpdate(e); // touched: collects (this game's hearts, subweapon...) and destroys the copy
        if (e->entityId) {
            DestroyEntity(e);
        }
        s_Mirrored[i] = false;
    }
}

// Authority: the guest took these drops.
static void ApplyTaken(void) {
    s32 i;
    Entity* e;

    for (i = 0; i < s_NTaken; i++) {
        e = &g_Entities[STAGE_ENTITY_START + s_Taken[i]];
        if (e->entityId == s_TakenId[i]) {
            DestroyEntity(e);
        }
    }
    s_NTaken = 0;
}

static u8 s_HpBefore[STAGE_SLOTS][8]; // guest: hit fields of the copies before hit detection

static void SaveHitFields(void) {
    s32 i;
    Entity* e;

    for (i = 0; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        *(s16*)&s_HpBefore[i][0] = e->hitPoints;
        s_HpBefore[i][2] = e->hitFlags;
        s_HpBefore[i][3] = (e->flags & FLAG_DEAD) != 0;
        s_HpBefore[i][4] = e->entityId != 0;
    }
}

// What the guest's hit detection created (drops, blood, soul orbs, damage numbers) would only
// live until the next snapshot: the authority creates them instead, for both worlds.
static void ReportSpawns(void) {
    s32 i, scrollX = g_Tilemap.scrollX.i.hi, scrollY = g_Tilemap.scrollY.i.hi;
    Entity* e;

    for (i = SPAWN_FIRST - STAGE_ENTITY_START; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (s_HpBefore[i][4] || !e->entityId || s_Mirrored[i] || s_Local[i]) {
            continue;
        }
        ProgressEmit(EV_SPAWN, e->entityId, (u32)e->pfnUpdate);
        ProgressEmit(EV_SPAWN2, e->params,
                     (u16)(e->posX.i.hi + scrollX) | (u32)(u16)(e->posY.i.hi + scrollY) << 16);
        ProgressEmit(EV_SPAWN3, (STAGE_ENTITY_START + i >= SPAWN_SECOND) | (u8)(e->velocityY >> 14) << 8,
                     e->ext.equipItemDrop.castleFlag);
    }
}

static void ReportHits(void) {
    s32 i, damage;
    Entity* e;

    for (i = 0; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (!s_Mirrored[i] || !e->entityId) {
            continue;
        }
        damage = *(s16*)&s_HpBefore[i][0] - e->hitPoints;
        if (!e->hitFlags && !e->hitParams && !damage && ((e->flags & FLAG_DEAD) != 0) == s_HpBefore[i][3]) {
            continue;
        }
        ProgressEmit(EV_HIT, i | (e->entityId << 8),
                     (u16)damage | (e->hitFlags << 16) | (((e->flags & FLAG_DEAD) != 0) << 24));
        ProgressEmit(EV_HIT2, i | (e->hitParams ? (e->hitParams & 0xFF ? e->hitParams & 0xFF : 0xFF) : 0) << 8,
                     e->nFramesInvincibility | (e->stunFrames & 0xFF) << 8 | (u32)e->hitEffect << 16);
    }
}

static void SpawnEvent(u8 type, u16 a, u32 b) {
    PendingSpawn* sp;

    if (type == EV_SPAWN) {
        if (s_NSpawns >= LEN(s_Spawns)) {
            return;
        }
        sp = &s_Spawns[s_NSpawns++];
        sp->entityId = a;
        sp->pfnUpdate = b;
        sp->parts = 1;
        sp->stage = g_StageId;
        return;
    }
    if (!s_NSpawns) {
        return;
    }
    sp = &s_Spawns[s_NSpawns - 1];
    if (type == EV_SPAWN2 && sp->parts == 1) {
        sp->params = a;
        sp->x = b & 0xFFFF;
        sp->y = b >> 16;
        sp->parts = 2;
    } else if (type == EV_SPAWN3 && sp->parts == 2) {
        sp->range = a & 1;
        sp->velocityY = (s8)(a >> 8) << 14;
        sp->castleFlag = b;
        sp->parts = 3;
    }
}

// Authority: create what the guest's hit detection created, as CreateEntityFromEntity does.
static void ApplySpawns(void) {
    PendingSpawn* sp;
    Entity* e;
    Entity* end;
    s32 i;

    for (i = 0; i < s_NSpawns; i++) {
        sp = &s_Spawns[i];
        if (sp->parts != 3 || sp->stage != g_StageId) {
            continue;
        }
        e = &g_Entities[sp->range ? SPAWN_SECOND : SPAWN_FIRST];
        end = sp->range ? &g_Entities[TOTAL_ENTITY_COUNT] : &g_Entities[SPAWN_SECOND - 32];
        while (e < end && e->entityId) {
            e++;
        }
        if (e == end) {
            continue; // full: the game would have skipped it too
        }
        DestroyEntity(e);
        e->entityId = sp->entityId;
        e->pfnUpdate = (PfnEntityUpdate)sp->pfnUpdate;
        e->posX.i.hi = sp->x - g_Tilemap.scrollX.i.hi;
        e->posY.i.hi = sp->y - g_Tilemap.scrollY.i.hi;
        e->params = sp->params;
        if (sp->castleFlag) {
            e->ext.equipItemDrop.castleFlag = sp->castleFlag;
        }
        e->velocityY = sp->velocityY; // drops pop up when they appear
    }
    s_NSpawns = 0;
}

void SharedHit(u8 type, u16 a, u32 b) {
    PendingHit* hit;
    s32 i;

    if (type == EV_SPAWN || type == EV_SPAWN2 || type == EV_SPAWN3) {
        SpawnEvent(type, a, b);
        return;
    }
    if (type == EV_TAKEN) {
        if (s_NTaken < LEN(s_Taken)) {
            s_Taken[s_NTaken] = a & 0xFF;
            s_TakenId[s_NTaken++] = a >> 8;
        }
        return;
    }

    if (type == EV_HIT) {
        if (s_NHits >= LEN(s_Hits)) {
            return;
        }
        hit = &s_Hits[s_NHits++];
        hit->slot = a & 0xFF;
        hit->entityId = a >> 8;
        hit->damage = (s16)(b & 0xFFFF);
        hit->hitFlags = (b >> 16) & 0xFF;
        hit->dead = (b >> 24) & 1;
        hit->second = false;
        return;
    }
    for (i = s_NHits - 1; i >= 0; i--) { // EV_HIT2 completes the latest hit on that slot
        if (s_Hits[i].slot == (a & 0xFF) && !s_Hits[i].second) {
            s_Hits[i].invincibility = b & 0xFF;
            s_Hits[i].stun = (b >> 8) & 0xFF;
            s_Hits[i].hitEffect = b >> 16;
            s_Hits[i].hitParams = a >> 8;
            s_Hits[i].second = true;
            return;
        }
    }
}

// Authority, right after its own hit detection: the guest's hits land on the real enemies,
// so their own update this frame flinches, dies and drops loot.
static void ApplyHits(void) {
    s32 i;
    PendingHit* hit;
    Entity* e;

    for (i = 0; i < s_NHits; i++) {
        hit = &s_Hits[i];
        e = &g_Entities[STAGE_ENTITY_START + hit->slot];
        if (e->entityId != hit->entityId) {
            continue; // gone, or the slot holds something else now
        }
        e->hitPoints -= hit->damage;
        if (hit->hitFlags > e->hitFlags) {
            e->hitFlags = hit->hitFlags;
        }
        if (hit->damage > 0 || hit->dead) {
            // The hit flash, as the game's own hit detection starts it (src/st/collision.h):
            // the stage update cycles the palette while flags & 0xF count down.
            if (!e->hitEffect && !(e->flags & 0xF)) {
                e->hitEffect = e->palette;
            }
            e->flags |= 0xF;
        }
        if (hit->second) {
            if (hit->invincibility > e->nFramesInvincibility) {
                e->nFramesInvincibility = hit->invincibility;
            }
            if (hit->stun > e->stunFrames) {
                e->stunFrames = hit->stun;
            }
            if (hit->hitEffect) {
                e->hitEffect = hit->hitEffect;
            }
            if (hit->hitParams && !e->hitParams) {
                e->hitParams = hit->hitParams; // a candle breaks on this
            }
        }
        if (hit->dead) { // the guest's hit detection killed its copy
            e->flags |= FLAG_DEAD;
            if (e->entityRoomIndex) { // what the game's own kill does (PreventEntityFromRespawning)
                g_unkGraphicsStruct.D_80097428[(e->entityRoomIndex - 1) >> 5] |=
                    1 << ((e->entityRoomIndex - 1) & 0x1F);
            }
        }
    }
    s_NHits = 0;
}

static void HitDetectionWrap(void) {
    if (s_Role == ROLE_GUEST) {
        SaveHitFields();
        s_HitDetection();
        CollectTouchedDrops();
        ReportHits();
        ReportSpawns();
        return;
    }
    s_HitDetection();
    if (s_Role == ROLE_AUTHORITY) {
        ApplyHits();
        ApplySpawns();
        ApplyTaken();
    } else {
        s_NHits = 0;
        s_NSpawns = 0;
        s_NTaken = 0;
    }
}

// --- targeting: the stage's helpers aim at the nearer player

static void NearestPlayer(s16* x, s16* y) {
    const CoopPresence* p = &g_CoopLink.partner;
    s32 px, py, ox, oy, dMe, dPartner;

    *x = PLAYER.posX.i.hi;
    *y = PLAYER.posY.i.hi;
    if (s_Role != ROLE_AUTHORITY) {
        return;
    }
    px = p->x - g_Tilemap.scrollX.i.hi; // partner, in this game's screen space
    py = p->y - g_Tilemap.scrollY.i.hi;
    ox = g_CurrentEntity->posX.i.hi;
    oy = g_CurrentEntity->posY.i.hi;
    dMe = ABS(*x - ox) + ABS(*y - oy);
    dPartner = ABS(px - ox) + ABS(py - oy);
    if (dPartner < dMe) {
        *x = px;
        *y = py;
    }
}

static u8 CoopGetSideToPlayer(void) {
    s16 x, y;
    u8 side = 0;

    NearestPlayer(&x, &y);
    if (g_CurrentEntity->posX.i.hi > x) {
        side |= 1;
    }
    if (g_CurrentEntity->posY.i.hi > y) {
        side |= 2;
    }
    return side;
}

static s16 CoopGetDistanceToPlayerX(void) {
    s16 x, y;

    NearestPlayer(&x, &y);
    return ABS(g_CurrentEntity->posX.i.hi - x);
}

static s32 CoopGetDistanceToPlayerY(void) {
    s16 x, y;

    NearestPlayer(&x, &y);
    return ABS(g_CurrentEntity->posY.i.hi - y);
}

#define J(target) (0x08000000 | (((u32)(target) & 0x0FFFFFFF) >> 2))

static bool s_Wrote;

static bool PatchOne(u32 addr, u32 firstWord, void* target) {
    u32* code = (u32*)addr;

    if (!addr) {
        return true; // nothing to patch in this overlay
    }
    if (code[0] == J(target)) {
        return true; // done already
    }
    if (code[0] != firstWord) {
        return false; // not the code we expect (yet: the overlay may still be loading)
    }
    code[0] = J(target);
    code[1] = 0; // nop (delay slot)
    s_Wrote = true;
    return true;
}

// Patch the overlay once all its code is there, and again whenever it's loaded again: a
// teleport or a respawn within the same stage reloads the same overlay from the CD, wiping the
// patches (same g_api.o.Update, so that alone can't tell). The first helper is the sentinel.
static const OverlayInfo* s_PatchedOvl;
static void PatchTargeting(void) {
    static void* const replacements[3] = {
        CoopGetSideToPlayer, CoopGetDistanceToPlayerX, CoopGetDistanceToPlayerY};
    const OverlayInfo* ovl;
    bool done = true;
    s32 i;

    if (g_api.o.Update == GuestUpdate) {
        return;
    }
    if ((void*)g_api.o.Update == s_PatchedFor &&
        (!s_PatchedOvl || *(u32*)s_PatchedOvl->helpers[0].addr == J(CoopGetSideToPlayer))) {
        return;
    }
    ovl = FindOverlay(g_StageId);
    s_PatchedOvl = NULL;
    if (!ovl) {
        s_PatchedFor = g_api.o.Update;
        return;
    }
    for (i = 0; i < 3; i++) {
        done &= PatchOne(ovl->helpers[i].addr, ovl->helpers[i].firstWord, replacements[i]);
    }
    // Solid entities: the module's copy records them (solid.c)
    done &= PatchOne(ovl->solid.addr, ovl->solid.firstWord, CoopPlayerCollision);
    if (s_Wrote) {
        FlushCache();
        s_Wrote = false;
    }
    if (done) {
        s_PatchedFor = g_api.o.Update;
        s_PatchedOvl = ovl->helpers[0].addr ? ovl : NULL;
    }
}

const OverlayInfo* FindOverlay(s32 stage) {
    const OverlayInfo* o;

    for (o = g_Overlays; o->stage >= 0; o++) {
        if (o->stage == stage) {
            return o;
        }
    }
    return NULL;
}

// --- per frame

void SharedUpdate(void) {
    TrackRoom();
    if (g_GameState != Game_Play) {
        return;
    }
    if (g_api.o.HitDetection != HitDetectionWrap && g_api.o.HitDetection) {
        s_HitDetection = g_api.o.HitDetection;
        g_api.o.HitDetection = HitDetectionWrap;
    }
    if (g_GameStep == Play_Default) {
        PatchTargeting();
        VramPatch();
    }
    DecideRole();
    VramRecord(s_Role == ROLE_AUTHORITY);
    SolidRecord(s_Role == ROLE_AUTHORITY);
    if (s_Role == ROLE_GUEST) {
        KeepStubbed();
        ApplySnapshot();
    }
}

void SharedAfterUpdate(void) {
    if (s_Role == ROLE_AUTHORITY && g_GameState == Game_Play && g_GameStep == Play_Default) {
        CaptureSnapshot();
    }
}

s32 SharedRole(void) { return s_Role; }

void SharedPresence(CoopPresence* p) {
    p->roomFrames = s_RoomFrames;
    p->scrollX = g_Tilemap.scrollX.i.hi;
    p->scrollY = g_Tilemap.scrollY.i.hi;
    p->role = s_Role;
}
