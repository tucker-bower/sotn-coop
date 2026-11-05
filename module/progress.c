// Shared progression: detect what this game unlocks, send it as events, and apply the
// partner's with the game's own functions (design/M2-shared-progression.md).
//
// Detection: shadow copies of the castle flags, the map and the gold, diffed every frame;
// plus wrappers on the two g_api entries every in-world find goes through (AddToInventory,
// func_800FE044). Applying an event updates the shadows, so nothing echoes back.
// Level is shared too (design/M11): a kill's XP is halved while a partner is linked, and what
// was gained goes to the partner, whose game levels up the normal way (CheckAndDoLevelUp).
#define COOP_MODULE
#include <game.h>
#include "flag_gated.h"
#include "coop_api.h"
#include "link.h"
#include "progress.h"
#include "message.h"
#include "boss.h"
#include "shared.h"

void AddToInventory(u16 id, EquipKind kind);                 // DRA
s32 func_800FE044(s32 amount, s32 type);                     // DRA: life/heart max up, relics, XP
void func_800F1B08(s32 tileX, s32 tileY, s32 arg2);          // DRA: draws one map cell
void RevealSecretPassageOnMap(s32 tileX, s32 tileY, s32 flag); // DRA
void DestroyEntity(Entity* entity);                          // DRA
extern s32 g_ExpNext[];                                      // DRA: XP for each level

#define GRANT_LIFE_UP 0x8000
#define GRANT_HEART_UP 0x4000
#define GRANT_RELIC 0x2000

// Stage entity ids shared by every stage (src/st/*/*.h)
#define E_RELIC_ORB 0x0B
#define E_PERSISTENT_ITEM_DROP 0x0C
#define PERSISTENT_DROP_FLAG(e) (*(u16*)((u8*)(e) + 0xB4)) // ET_PersistentDrop.unkB4
extern const u16 g_Collectibles[]; // collectibles.c (scripts/gen_collectibles.py)
extern const s32 g_NCollectibles;
#define COLLECT_LIFE_VESSEL 1
#define COLLECT_HEART_VESSEL 2

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
// Boss kills (design/M5): a boss room's teleport checks the time attack record, so a boss
// beaten in one world must be recorded in the other too, or it'd be fought again there.
static s32 s_Records[TIMEATTACK_EVENT_END];
static s32 s_Visited;
#define RECORD_VISITED 0xFFFF // EV_RECORD a: the visited bits (D_8003CB00), not a record
static bool s_InPlay;  // last frame was in play: the shadows are valid
static bool s_PartnerGone; // no word from the partner for PARTNER_GONE_FRAMES
#define PARTNER_GONE_FRAMES 300
static u16 s_Changed[16]; // castle flags the partner changed this frame
static s32 s_NChanged;
static bool s_Applying; // the wrappers ignore our own calls
static void (*s_AddToInventory)(u16, EquipKind);
static s32 (*s_Grant)(s32, s32);
static u16 (*s_DealDamage)(Entity*, Entity*);

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

bool ProgressEmit(u8 type, u16 a, u32 b) { return Emit(type, a, b); }

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

static bool CollectingA(u16 entityId) {
    Entity* e = g_CurrentEntity;

    return e >= &g_Entities[STAGE_ENTITY_START] && e < &g_Entities[TOTAL_ENTITY_COUNT] && e->entityId == entityId;
}

// An item an enemy dropped (#156): one kill, one item, for whoever takes it. Shared, it gave
// every player a copy. Placed items (params 0x8000) are finds, and stay shared (D37).
static bool EnemyDrop(void) { return CollectingA(E_EQUIP_ITEM_DROP) && !(g_CurrentEntity->params & 0x8000); }

// A placed collectible (items, vessels) reaches the partner as its castle flag, not as an event:
// the flag also comes with a reconnect, so a find a player made and didn't save isn't lost (#154).
static bool PlacedFind(void) { return CollectingA(E_PERSISTENT_ITEM_DROP); }

static void AddToInventoryWrap(u16 id, EquipKind kind) {
    s_AddToInventory(id, kind);
    if (!s_Applying && !EnemyDrop() && !PlacedFind()) {
        Emit(EV_ITEM, id, kind);
    }
}

// Duo balancing, like 2x boss HP (boss.c): a partner's game was heard from in the last 10 s
static bool PartnerLinked(void) { return g_CoopLink.partnerAge < 600; }

static s32 GrantWrap(s32 amount, s32 type) {
    // anything else with an amount is a kill's XP (type: the enemy's level)
    bool kill = amount != 0 && type != GRANT_LIFE_UP && type != GRANT_HEART_UP && type != GRANT_RELIC;
    s32 exp = g_Status.exp;
    s32 ret;

    if (kill && !s_Applying) {
        amount = amount * RULE_PCT(expPct, 100) / 100;
        if (PartnerLinked() && !RULE_OFF(RULE_NO_SHARED_LEVEL)) {
            amount /= 2; // before the game scales it by the level gap
        }
        amount = amount > 1 ? amount : 1;
    }
    ret = s_Grant(amount, type);
    if (!s_Applying && ret == 0 && !PlacedFind() &&
        (type == GRANT_LIFE_UP || type == GRANT_HEART_UP || type == GRANT_RELIC)) {
        Emit(EV_GRANT, type, amount);
    }
    if (kill && !s_Applying && (s32)g_Status.exp > exp && !RULE_OFF(RULE_NO_SHARED_LEVEL)) {
        Emit(EV_EXP, 0, g_Status.exp - exp);
    }
    return ret;
}

// The castle's damage rule (D162). The result's top two bits are DealDamage's flags (immune,
// absorbed); the rest is the damage.
static u16 DealDamageWrap(Entity* enemy, Entity* attacker) {
    u16 r = s_DealDamage(enemy, attacker);
    s32 pct = RULE_PCT(dealtPct, 100);
    s32 n = r & 0x3FFF;

    if (pct != 100 && n) {
        n = n * pct / 100;
        r = (r & 0xC000) | (n < 1 ? 1 : n > 0x3FFF ? 0x3FFF : n);
    }
    return r;
}

// Damage to this game's player. Hit detection left it in PLAYER.hitPoints last frame (PvP this
// frame), and the player's update takes it in this frame's UpdateGame: scaled here, every
// character's own damage code does the rest. Alucard's code then takes off his defense, so the
// rule scales what's left after it: 50% is half of what he'd lose.
void ProgressDamageTaken(void) {
    static s32 s_Scaled = -1; // the hit already scaled, if the player's update hasn't taken it
    s32 pct = RULE_PCT(takenPct, 100);
    s32 hit = PLAYER.hitPoints;
    s32 def = g_CoopCharacter == PLAYER_ALUCARD ? g_Status.defenseEquip : 0;

    if (!PLAYER.hitParams || !hit) {
        s_Scaled = -1;
    } else if (pct != 100 && g_GameState == Game_Play && hit != s_Scaled && hit > def) {
        hit = def + (hit - def) * pct / 100;
        s_Scaled = PLAYER.hitPoints = hit > def ? hit : def + 1;
    }
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
    if (g_api.DealDamage != DealDamageWrap) {
        s_DealDamage = g_api.DealDamage;
        g_api.DealDamage = DealDamageWrap;
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

static void DetectRecords(void) {
    s32 i;

    for (i = 0; i < TIMEATTACK_EVENT_END; i++) {
        if (g_Settings.timeAttackRecords[i] != s_Records[i]) {
            if (g_Settings.timeAttackRecords[i] && !Emit(EV_RECORD, i, g_Settings.timeAttackRecords[i])) {
                return;
            }
            s_Records[i] = g_Settings.timeAttackRecords[i];
        }
    }
    if (g_Settings.D_8003CB00 != s_Visited && Emit(EV_RECORD, RECORD_VISITED, g_Settings.D_8003CB00)) {
        s_Visited = g_Settings.D_8003CB00;
    }
}

static void DetectGold(void) {
    if (RULE_OFF(RULE_NO_SHARED_GOLD)) {
        s_Gold = g_Status.gold; // turned back on: only what changes from then on is shared
    } else if (g_Status.gold != s_Gold && Emit(EV_GOLD, 0, g_Status.gold - s_Gold)) {
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

// The partner's game has taken placed collectibles this one hasn't (#154): live, or before this
// player reconnected without saving. This player gets their own, as D37 shares every find.
static void Collect(s32 idx, u8 added) {
    s32 bit, flag;
    u16 c;
    const u8* name;

    for (bit = 0; bit < 8; bit++) {
        flag = (idx - FLAG_COLLECTIBLES) * 8 + bit;
        if (!(added & (1 << bit)) || flag >= g_NCollectibles || !(c = g_Collectibles[flag])) {
            continue;
        }
        if (c == COLLECT_LIFE_VESSEL || c == COLLECT_HEART_VESSEL) {
            func_800FE044(5, c == COLLECT_LIFE_VESSEL ? GRANT_LIFE_UP : GRANT_HEART_UP);
            continue;
        }
        AddToInventory(c & 0x3FFF, c & 0x8000 ? EQUIP_HAND : EQUIP_ARMOR);
        name = c & 0x8000 ? (const u8*)g_api.equipDefs[c & 0x3FFF].name : (const u8*)g_api.accessoryDefs[c & 0x3FFF].name;
        CoopMessageName(name);
    }
}

static void Apply(const CoopEvent* ev) {
    s32 delta;

    s_Applying = true;
    switch (ev->type) {
    case EV_FLAG:
        if (ev->a < LEN(g_CastleFlags) && !IsExcluded(ev->a)) {
            u8 merged = MergeFlag(ev->a, g_CastleFlags[ev->a], ev->b);
            if (merged != g_CastleFlags[ev->a] && s_NChanged < LEN(s_Changed)) {
                s_Changed[s_NChanged++] = ev->a;
            }
            if (ev->a >= FLAG_COLLECTIBLES && !IsCounter(ev->a)) {
                Collect(ev->a, merged & ~g_CastleFlags[ev->a]);
            }
            g_CastleFlags[ev->a] = merged;
            s_Flags[ev->a] = merged;
        }
        break;
    case EV_MAP:
        if (ev->a < LEN(g_CastleMap)) {
            ApplyMap(ev->a, ev->b);
        }
        break;
    case EV_ITEM:
        AddToInventory(ev->a, ev->b);
        // The game whose copy took it showed its name; here it arrives unannounced (playtest 0.14).
        CoopMessageName(ev->b == EQUIP_HAND ? (const u8*)g_api.equipDefs[ev->a].name
                                            : (const u8*)g_api.accessoryDefs[ev->a].name);
        break;
    case EV_USED: // the partner used it up (M13's fairy revive): one fewer in the shared bag
        if (ev->a < LEN(g_Status.equipHandCount) && g_Status.equipHandCount[ev->a]) {
            g_Status.equipHandCount[ev->a]--;
        }
        break;
    case EV_KILLED:
        BossKilled(ev->a, ev->b);
        break;
    case EV_GRANT:
        func_800FE044(ev->b, ev->a);
        // Like the relic orb does: familiar cards arrive switched off.
        if (ev->a == GRANT_RELIC && ev->b >= RELIC_SWORD_CARD && ev->b < RELIC_FAERIE_CARD) {
            g_Status.relics[ev->b] ^= RELIC_FLAG_ACTIVE;
        }
        break;
    case EV_HIT:
    case EV_HIT2:
    case EV_SPAWN:
    case EV_SPAWN2:
    case EV_SPAWN3:
    case EV_TAKEN:
        SharedHit(ev->type, ev->a, ev->b);
        break;
    case EV_RECORD: // the first record stands (it's when the boss was first beaten)
        if (ev->a == RECORD_VISITED) {
            g_Settings.D_8003CB00 |= ev->b;
            s_Visited = g_Settings.D_8003CB00;
        } else if (ev->a < TIMEATTACK_EVENT_END && !g_Settings.timeAttackRecords[ev->a]) {
            g_Settings.timeAttackRecords[ev->a] = ev->b;
            s_Records[ev->a] = ev->b;
        }
        break;
    case EV_EXP: // the game's own level-up check sees it next frame
        if (g_Status.level < 99) {
            g_Status.exp += ev->b;
            if ((s32)g_Status.exp > g_ExpNext[99]) {
                g_Status.exp = g_ExpNext[99];
            }
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

// The partner changed flags that objects in this room were built from (walls, doors,
// switches): run their init again so they read the new state (design/M2, part 3).
static bool ReadsChangedFlag(const FlagGated* g) {
    s32 i, j;

    for (i = 0; i < g->nFlags; i++) {
        for (j = 0; j < s_NChanged; j++) {
            if (g->flags[i] == FLAG_GATED_ANY || g->flags[i] == s_Changed[j]) {
                return true;
            }
        }
    }
    return false;
}

static void RefreshGated(void) {
    const FlagGated* g;
    Entity* e;

    for (e = &g_Entities[STAGE_ENTITY_START]; e < &g_Entities[TOTAL_ENTITY_COUNT]; e++) {
        // Empty, or not initialized yet. (No enemy filter: breakable walls use the enemy fields
        // to be hittable. The table itself only holds flag-reading object types.)
        if (!e->entityId || !e->step) {
            continue;
        }
        for (g = g_FlagGated; g->stage >= 0; g++) {
            if (g->stage == g_StageId && g->entityId == e->entityId && ReadsChangedFlag(g)) {
                if (e->flags & FLAG_HAS_PRIMS) {
                    g_api.FreePrimitives(e->primIndex);
                    e->flags &= ~FLAG_HAS_PRIMS;
                }
                e->step = 0;
                e->step_s = 0;
                break;
            }
        }
    }
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
    if (s_NChanged) {
        RefreshGated();
        s_NChanged = 0;
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
    for (i = 0; i < TIMEATTACK_EVENT_END; i++) {
        s_Records[i] = 0;
    }
    s_Visited = 0;
}

// Death's scene takes Alucard's gear from the players who see it, but the flag it sets also comes
// with a save or a partner's castle: a player joining later kept the set (playtest 0.14). Looked at
// when a game comes into play, and before the inverted castle: it has the pieces to find again.
static void RobbedUpdate(void) {
    const u32* eq = g_Status.equipment;

    if (g_CastleFlags[IVE_BEEN_ROBBED] && !g_CastleFlags[INVERTED_CASTLE_UNLOCKED] && !g_CutsceneHasControl &&
        g_StageId != STAGE_ST0 && !(g_StageId & STAGE_INVERTEDCASTLE_FLAG) &&
        (eq[LEFT_HAND_SLOT] == ITEM_ALUCARD_SWORD || eq[RIGHT_HAND_SLOT] == ITEM_ALUCARD_SHIELD ||
         eq[LEFT_HAND_SLOT] == ITEM_ALUCARD_SHIELD || eq[RIGHT_HAND_SLOT] == ITEM_ALUCARD_SWORD ||
         eq[HEAD_SLOT] == ITEM_DRAGON_HELM || eq[ARMOR_SLOT] == ITEM_ALUCARD_MAIL ||
         eq[CAPE_SLOT] == ITEM_TWILIGHT_CLOAK || eq[ACCESSORY_1_SLOT] == ITEM_NECKLACE_OF_J ||
         eq[ACCESSORY_2_SLOT] == ITEM_NECKLACE_OF_J)) {
        g_api.InitStatsAndGear(1);
    }
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
        RobbedUpdate();
    }
    // A partner back after 5 s away may have restarted from an older save: send everything
    // again, so they catch up on what was found meanwhile, or taken and not saved (#154).
    if (g_CoopLink.partnerAge > PARTNER_GONE_FRAMES) {
        s_PartnerGone = true;
    } else if (s_PartnerGone && g_CoopLink.partnerAge <= 30) {
        s_PartnerGone = false;
        Resync();
    }
    DetectFlags();
    DetectMap();
    DetectGold();
    DetectRecords();
    ApplyInbox();
}
