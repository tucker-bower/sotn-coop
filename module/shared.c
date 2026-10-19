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
#include "progress.h"
#include "shared.h"

s32 AllocPrimitives(u8 type, s32 count); // DRA
void FreePrimitives(s32 index);          // DRA
void DestroyEntity(Entity* entity);      // DRA
void FlushCache(void);                   // main.exe

#define STAGE_SLOTS (TOTAL_ENTITY_COUNT - STAGE_ENTITY_START)
#define ABS(x) ((x) < 0 ? -(x) : (x))
#define ROLE_SETTLE 4      // frames a role change must hold before it happens
#define MAX_PRIMS_PER_ENTITY 64
#define CAMERA_NEAR 256    // shared only while the cameras are within a screen of each other

typedef struct {
    u16 stage;
    s16 roomLeft, roomTop;
    s16 scrollX, scrollY;
    u16 nEntities;
    u16 bssSize;
    u16 pad;
} SnapHeader;

typedef struct {
    u8 slot;   // 0..191 (+ STAGE_ENTITY_START)
    u8 nPrims; // primitives that follow the entity
    u16 pad;
} SnapEntity;

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
static u32 s_AppliedSeq;

// Hit detection wrapper, and hits the guest made (authority applies them)
static void (*s_HitDetection)(void);
typedef struct {
    u8 slot;
    u16 entityId;
    s16 damage;
    u8 hitFlags, dead, invincibility, stun;
    u16 hitEffect;
    bool second; // the EV_HIT2 half arrived
} PendingHit;
static PendingHit s_Hits[32];
static s32 s_NHits;

// Targeting patch: which overlay was patched last
static void* s_PatchedFor;

static void Stub(void) {}

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
    }
    s_OrigUpdate = g_api.o.Update;
    s_OrigSpawner = g_api.o.UpdateRoomPosition;
    s_AppliedSeq = g_CoopLink.snapInSeq;
}

// The copies become this game's own world: their primitives are theirs now, and the stage
// logic runs them from here (that's the hand-over: design/M4, part 1).
static void StopBeingGuest(void) {
    if (g_api.o.Update == Stub) {
        g_api.o.Update = s_OrigUpdate;
    }
    if (g_api.o.UpdateRoomPosition == Stub) {
        g_api.o.UpdateRoomPosition = s_OrigSpawner;
    }
}

static void KeepStubbed(void) {
    if (g_api.o.Update != Stub) { // a fresh overlay load rewrote the table
        s_OrigUpdate = g_api.o.Update;
        g_api.o.Update = Stub;
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
}

static void ApplySnapshot(void) {
    const u8* r = g_CoopLink.snapIn;
    const u8* end = g_CoopLink.snapIn + g_CoopLink.snapInSize;
    const SnapHeader* h = (const SnapHeader*)r;
    const OverlayInfo* ovl;
    u8 present[STAGE_SLOTS];
    s32 i, k, dx, dy, n, idx = -1;
    Entity* e;
    Primitive* p;
    Primitive* next;

    if (g_CoopLink.snapInSeq == s_AppliedSeq || g_CoopLink.snapInSize < sizeof(SnapHeader) ||
        h->stage != g_StageId || h->roomLeft != g_Tilemap.left || h->roomTop != g_Tilemap.top) {
        return; // nothing new, or not this room's
    }
    s_AppliedSeq = g_CoopLink.snapInSeq;
    dx = h->scrollX - g_Tilemap.scrollX.i.hi;
    dy = h->scrollY - g_Tilemap.scrollY.i.hi;
    r += sizeof(SnapHeader);

    for (i = 0; i < STAGE_SLOTS; i++) {
        present[i] = false;
    }
    for (k = 0; k < h->nEntities && r + sizeof(SnapEntity) + sizeof(Entity) <= end; k++) {
        const SnapEntity* se = (const SnapEntity*)r;
        const Primitive* src;

        r += sizeof(SnapEntity);
        i = se->slot;
        present[i] = true;
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (!s_Mirrored[i] && e->entityId) {
            DestroyEntity(e);
        }
        CopyWords(e, r, sizeof(Entity));
        r += sizeof(Entity);
        s_Mirrored[i] = true;
        src = (const Primitive*)r;
        n = se->nPrims;
        r += n * sizeof(Primitive);
        e->flags &= ~FLAG_HAS_PRIMS;
        if (n != s_MirrorCount[i]) { // keep last frame's chain if it's the right length
            FreeMirrorPrims(i);
            if (n && (idx = AllocPrimitives(src->type & 0xF, n)) >= 0) {
                s_MirrorPrims[i] = idx;
                s_MirrorCount[i] = n;
            }
        }
        if (n && s_MirrorPrims[i] >= 0 && r <= end) {
            for (p = &g_PrimBuf[s_MirrorPrims[i]]; p && n--; p = next, src++) {
                next = p->next;
                CopyWords(p, src, sizeof(Primitive));
                p->next = next;
                if (e->flags & FLAG_POS_CAMERA_LOCKED) {
                    ShiftPrim(p, dx, dy);
                }
            }
            e->primIndex = s_MirrorPrims[i];
            e->flags |= FLAG_HAS_PRIMS;
        }
        if (e->unk68) {
            e->posX.val += dx * e->unk68 * 0x100;
            e->posY.val += dy * e->unk68 * 0x100;
        } else if (e->flags & FLAG_POS_CAMERA_LOCKED) {
            e->posX.i.hi += dx;
            e->posY.i.hi += dy;
        }
    }
    for (i = 0; i < STAGE_SLOTS; i++) {
        if (!present[i]) {
            ClearSlot(i);
        }
    }
    ovl = FindOverlay(g_StageId);
    if (ovl && h->bssSize == ovl->bssSize && r + h->bssSize <= end) {
        CopyWords((void*)ovl->bssStart, r, h->bssSize);
    }
}

// --- authority

static void CaptureSnapshot(void) {
    u8* w = g_CoopLink.snapOut;
    u8* end = g_CoopLink.snapOut + SNAP_MAX;
    SnapHeader* h = (SnapHeader*)w;
    const OverlayInfo* ovl = FindOverlay(g_StageId);
    s32 i, n;
    Entity* e;
    Primitive* p;

    h->stage = g_StageId;
    h->roomLeft = g_Tilemap.left;
    h->roomTop = g_Tilemap.top;
    h->scrollX = g_Tilemap.scrollX.i.hi;
    h->scrollY = g_Tilemap.scrollY.i.hi;
    h->nEntities = 0;
    h->bssSize = 0;
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
        ((SnapEntity*)w)->slot = i;
        ((SnapEntity*)w)->nPrims = n;
        w += sizeof(SnapEntity);
        CopyWords(w, e, sizeof(Entity));
        w += sizeof(Entity);
        for (p = n ? &g_PrimBuf[e->primIndex] : NULL; p && n--; p = p->next) {
            CopyWords(w, p, sizeof(Primitive));
            w += sizeof(Primitive);
        }
        h->nEntities++;
    }
    if (ovl && w + ovl->bssSize <= end) {
        CopyWords(w, (void*)ovl->bssStart, ovl->bssSize);
        w += ovl->bssSize;
        h->bssSize = ovl->bssSize;
    }
    g_CoopLink.snapOutSize = w - g_CoopLink.snapOut;
    g_CoopLink.snapOutSeq++;
}

// --- hits

static u8 s_HpBefore[STAGE_SLOTS][8]; // guest: hit fields of the copies before hit detection

static void SaveHitFields(void) {
    s32 i;
    Entity* e;

    for (i = 0; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        *(s16*)&s_HpBefore[i][0] = e->hitPoints;
        s_HpBefore[i][2] = e->hitFlags;
        s_HpBefore[i][3] = (e->flags & FLAG_DEAD) != 0;
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
        if (!e->hitFlags && !damage && ((e->flags & FLAG_DEAD) != 0) == s_HpBefore[i][3]) {
            continue;
        }
        ProgressEmit(EV_HIT, i | (e->entityId << 8),
                     (u16)damage | (e->hitFlags << 16) | (((e->flags & FLAG_DEAD) != 0) << 24));
        ProgressEmit(EV_HIT2, i, e->nFramesInvincibility | (e->stunFrames & 0xFF) << 8 |
                                     (u32)e->hitEffect << 16);
    }
}

void SharedHit(u8 type, u16 a, u32 b) {
    PendingHit* hit;
    s32 i;

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
        }
        if (hit->dead) { // the guest's hit detection killed its copy
            e->flags |= FLAG_DEAD;
        }
    }
    s_NHits = 0;
}

static void HitDetectionWrap(void) {
    if (s_Role == ROLE_GUEST) {
        SaveHitFields();
        s_HitDetection();
        ReportHits();
        return;
    }
    s_HitDetection();
    if (s_Role == ROLE_AUTHORITY) {
        ApplyHits();
    } else {
        s_NHits = 0;
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

static void PatchTargeting(void) {
    static void* const replacements[3] = {
        CoopGetSideToPlayer, CoopGetDistanceToPlayerX, CoopGetDistanceToPlayerY};
    const OverlayInfo* ovl;
    u32* code;
    s32 i;

    if ((void*)g_api.o.Update == s_PatchedFor || g_api.o.Update == Stub) {
        return;
    }
    s_PatchedFor = g_api.o.Update; // each overlay load writes its own Update into g_api.o
    ovl = FindOverlay(g_StageId);
    if (!ovl) {
        return;
    }
    for (i = 0; i < 3; i++) {
        code = (u32*)ovl->helpers[i].addr;
        if (code[0] != ovl->helpers[i].firstWord) {
            continue; // not the code we expect: leave it alone
        }
        code[0] = J(replacements[i]);
        code[1] = 0; // nop (delay slot)
    }
    FlushCache();
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
    }
    DecideRole();
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

void SharedPresence(CoopPresence* p) {
    p->roomFrames = s_RoomFrames;
    p->scrollX = g_Tilemap.scrollX.i.hi;
    p->scrollY = g_Tilemap.scrollY.i.hi;
    p->role = s_Role;
}
