// Shared progression: detect what this game unlocks, send it as events, and apply the
// partner's with the game's own functions (design/M2-shared-progression.md).
//
// Detection: shadow copies of the castle flags, the map and the gold, diffed every frame;
// plus wrappers on the two g_api entries every in-world find goes through (AddToInventory,
// func_800FE044). Applying an event updates the shadows, so nothing echoes back.
#define COOP_MODULE
#include <game.h>
#include "link.h"
#include "progress.h"

void AddToInventory(u16 id, EquipKind kind);                 // DRA
s32 func_800FE044(s32 amount, s32 type);                     // DRA: life/heart max up, relics, XP
void func_800F1B08(s32 tileX, s32 tileY, s32 arg2);          // DRA: draws one map cell
void RevealSecretPassageOnMap(s32 tileX, s32 tileY, s32 flag); // DRA
void DestroyEntity(Entity* entity);                          // DRA

#define GRANT_LIFE_UP 0x8000
#define GRANT_HEART_UP 0x4000
#define GRANT_RELIC 0x2000

// Stage entity ids shared by every stage (src/st/*/*.h)
#define E_RELIC_ORB 0x0B
#define E_PERSISTENT_ITEM_DROP 0x0C
#define PERSISTENT_DROP_FLAG(e) (*(u16*)((u8*)(e) + 0xB4)) // ET_PersistentDrop.unkB4

// Castle flags that aren't progress, and the two that count up (castle_flags.h).
#define FLAG_NO1_WEATHER 0x13
#define FLAG_NO1_BIRD_CYCLE 0x14
#define FLAG_PROLOGUE_COMPLETE 0x34
#define FLAG_NO4_WATER_BLOCKED 0xC1
#define FLAG_NO4_SKELETON_APE_AND_BRIDGE 0xC7
#define FLAG_COLLECTIBLES 0x100

static u8 s_Flags[LEN(g_CastleFlags)] __attribute__((aligned(4)));
static u8 s_Map[LEN(g_CastleMap)] __attribute__((aligned(4)));
static s32 s_Gold;
static bool s_InPlay;  // last frame was in play: the shadows are valid
static bool s_Applying; // the wrappers ignore our own calls
static void (*s_AddToInventory)(u16, EquipKind);
static s32 (*s_Grant)(s32, s32);

static bool Emit(u8 type, u16 a, u32 b) {
    CoopRing* r = &g_CoopLink.out;
    CoopEvent* ev;

    if (r->head - r->tail >= COOP_RING_SIZE) {
        g_CoopLink.dropped++;
        return false;
    }
    ev = &r->ev[r->head % COOP_RING_SIZE];
    ev->type = type;
    ev->a = a;
    ev->b = b;
    r->head++;
    return true;
}

static bool IsExcluded(s32 i) {
    return i == FLAG_NO1_WEATHER || i == FLAG_NO1_BIRD_CYCLE || i == FLAG_PROLOGUE_COMPLETE;
}

static bool IsCounter(s32 i) {
    return i == FLAG_NO4_WATER_BLOCKED || i == FLAG_NO4_SKELETON_APE_AND_BRIDGE;
}

static u8 MergeFlag(s32 i, u8 mine, u8 theirs) {
    if (IsCounter(i)) {
        return mine > theirs ? mine : theirs;
    }
    return mine | theirs;
}

static void AddToInventoryWrap(u16 id, EquipKind kind) {
    s_AddToInventory(id, kind);
    if (!s_Applying) {
        Emit(EV_ITEM, id, kind);
    }
}

static s32 GrantWrap(s32 amount, s32 type) {
    s32 ret = s_Grant(amount, type);
    if (!s_Applying && ret == 0 &&
        (type == GRANT_LIFE_UP || type == GRANT_HEART_UP || type == GRANT_RELIC)) {
        Emit(EV_GRANT, type, amount);
    }
    return ret;
}

// MainGame fills g_api from DRA's table before the main loop: wrap the two entries once
// they're there (and again if anything ever restores them).
static void WrapApi(void) {
    if (g_api.AddToInventory != (void*)AddToInventoryWrap) {
        s_AddToInventory = (void*)g_api.AddToInventory;
        g_api.AddToInventory = (void*)AddToInventoryWrap;
    }
    if (g_api.func_800FE044 != GrantWrap) {
        s_Grant = g_api.func_800FE044;
        g_api.func_800FE044 = GrantWrap;
    }
}

// --- detection: what changed in this game since last frame

// Both scans run every frame over 0xB00 bytes, so they compare a word at a time and only
// look at bytes where a word changed: about 3k cycles a frame instead of 30k+, which matters
// in scenes that already use most of a frame (a dropped frame changes how the game plays).
static void DetectFlags(void) {
    u32* cur = (u32*)g_CastleFlags;
    u32* old = (u32*)s_Flags;
    s32 w, i;
    u8 now, was;

    for (w = 0; w < LEN(g_CastleFlags) / 4; w++) {
        if (cur[w] == old[w]) {
            continue;
        }
        for (i = w * 4; i < w * 4 + 4; i++) {
            now = g_CastleFlags[i];
            was = s_Flags[i];
            if (now == was) {
                continue;
            }
            if (!IsExcluded(i) && (IsCounter(i) ? now > was : (now & ~was) != 0)) {
                if (!Emit(EV_FLAG, i, now)) {
                    return; // ring full: retry next frame
                }
            }
            s_Flags[i] = now;
        }
    }
}

static void DetectMap(void) {
    u32* cur = (u32*)g_CastleMap;
    u32* old = (u32*)s_Map;
    s32 w, i;
    u8 added;

    for (w = 0; w < LEN(g_CastleMap) / 4; w++) {
        if (cur[w] == old[w]) {
            continue;
        }
        for (i = w * 4; i < w * 4 + 4; i++) {
            added = g_CastleMap[i] & ~s_Map[i];
            if (added && !Emit(EV_MAP, i, added)) {
                return;
            }
            s_Map[i] = g_CastleMap[i];
        }
    }
}

static void DetectGold(void) {
    if (g_Status.gold != s_Gold && Emit(EV_GOLD, 0, g_Status.gold - s_Gold)) {
        s_Gold = g_Status.gold;
    }
}

// --- application: the partner's event, through the game's own code

// The partner took something this room still shows: remove it, with no reward.
// (A despawned item drop keeps its icon slot until the next stage load; slots are per stage.)
static void DespawnTaken(void) {
    Entity* e;
    u16 index;

    for (e = &g_Entities[STAGE_ENTITY_START]; e < &g_Entities[TOTAL_ENTITY_COUNT]; e++) {
        if (!e->step || e->step >= 5) { // not initialized yet, or already being collected
            continue;
        }
        if (e->entityId == E_RELIC_ORB) {
            if (g_Status.relics[e->params & 0x7FFF] & RELIC_FLAG_FOUND) {
                DestroyEntity(e);
            }
        } else if (e->entityId == E_PERSISTENT_ITEM_DROP) {
            index = PERSISTENT_DROP_FLAG(e);
            if ((g_CastleFlags[(index >> 3) + FLAG_COLLECTIBLES] >> (index & 7)) & 1) {
                DestroyEntity(e);
            }
        }
    }
}

static void ApplyMap(s32 idx, u8 bits) {
    s32 cell, x, y, inverted;
    u8 added = bits & ~g_CastleMap[idx];

    g_CastleMap[idx] |= bits;
    s_Map[idx] = g_CastleMap[idx];
    inverted = idx >= 0x400;
    for (cell = 0; cell < 4; cell++) {
        u8 explored = 1 << ((3 - cell) * 2); // low bit of the cell's pair
        x = (idx & 15) * 4 + cell;
        y = (idx & 0x3FF) >> 4;
        if (added & explored) {
            g_RoomCount++;
        }
        // Draw it now if it's in the castle being shown; the other castle is redrawn
        // from g_CastleMap when the player gets there.
        if (inverted != !!(g_StageId & STAGE_INVERTEDCASTLE_FLAG)) {
            continue;
        }
        if (added & explored) {
            func_800F1B08(x, y, 0);
            RevealSecretPassageOnMap(x, y, 0xFFFF);
        } else if ((added & (explored << 1)) && !(g_CastleMap[idx] & explored)) {
            func_800F1B08(x, y, 1);
        }
    }
}

static void Apply(const CoopEvent* ev) {
    s32 delta;

    s_Applying = true;
    switch (ev->type) {
    case EV_FLAG:
        if (ev->a < LEN(g_CastleFlags) && !IsExcluded(ev->a)) {
            g_CastleFlags[ev->a] = MergeFlag(ev->a, g_CastleFlags[ev->a], ev->b);
            s_Flags[ev->a] = g_CastleFlags[ev->a];
        }
        break;
    case EV_MAP:
        if (ev->a < LEN(g_CastleMap)) {
            ApplyMap(ev->a, ev->b);
        }
        break;
    case EV_ITEM:
        AddToInventory(ev->a, ev->b);
        break;
    case EV_GRANT:
        func_800FE044(ev->b, ev->a);
        // Like the relic orb does: familiar cards arrive switched off.
        if (ev->a == GRANT_RELIC && ev->b >= RELIC_SWORD_CARD && ev->b < RELIC_FAERIE_CARD) {
            g_Status.relics[ev->b] ^= RELIC_FLAG_ACTIVE;
        }
        break;
    case EV_GOLD:
        delta = (s32)ev->b;
        g_Status.gold += delta;
        if (g_Status.gold < 0) {
            g_Status.gold = 0;
        }
        s_Gold = g_Status.gold;
        break;
    }
    s_Applying = false;
}

static void ApplyInbox(void) {
    CoopRing* r = &g_CoopLink.in;
    bool any = false;

    while (r->tail != r->head) {
        Apply(&r->ev[r->tail % COOP_RING_SIZE]);
        r->tail++;
        any = true;
    }
    if (any) {
        DespawnTaken();
    }
}

static void Resync(void) {
    s32 i;

    for (i = 0; i < LEN(g_CastleFlags); i++) {
        s_Flags[i] = 0; // flags and map are a union: send everything once
    }
    for (i = 0; i < LEN(g_CastleMap); i++) {
        s_Map[i] = 0;
    }
    s_Gold = g_Status.gold; // gold is a delta: start counting from here
}

void ProgressUpdate(void) {
    bool inPlay = g_GameState == Game_Play && g_GameStep == Play_Default;

    WrapApi();
    if (!inPlay) {
        s_InPlay = false;
        return; // events wait in the inbox until the game is in play again
    }
    if (!s_InPlay) {
        s_InPlay = true;
        Resync();
    }
    DetectFlags();
    DetectMap();
    DetectGold();
    ApplyInbox();
}
