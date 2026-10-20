// Bosses together (design/M5-bosses-cutscenes.md).
//
// - A boss is any stage entity whose enemy definition is one of the bosses below. Boss fights
//   happen both in boss overlays (BO*, RBO*) and in ordinary stages (Slogra and Gaibon), so the
//   enemy is the test, not the stage.
// - Bosses have twice their HP while a partner is linked (D25): the in-RAM enemy table is
//   patched, so every boss spawned meanwhile gets it from InitializeEntity.
// - Aggro (D47): a boss goes for one player at a time and may switch after each of its
//   attacks. While its target is the partner, the boss's update runs with the partner standing
//   where the player is (PLAYER's position and facing, g_PlayerX/Y), then everything is put
//   back. That works for every boss, also the ones that read PLAYER directly instead of
//   calling the targeting helpers.
#define COOP_MODULE
#include <game.h>
#include "boss.h"
#include "link.h"
#include "shared.h"

#define STAGE_SLOTS (TOTAL_ENTITY_COUNT - STAGE_ENTITY_START)
#define AGGRO_PERIOD 180 // frames between re-rolls of a boss's target (about one attack)
#define AGGRO_SWITCH 128     // out of 256: the chance to switch after an attack (50%)
#define HP_MAX 0x7FFF

// Enemy definition indices of the bosses (assets/dra/us/enemydefs.yaml). Regular enemies
// with a lot of HP (Discus Lord, Guardian...) aren't here; neither is the prologue's Dracula
// (the prologue is solo).
static const u16 s_Bosses[] = {
    23,  // Lesser Demon
    50,  // Olrox
    198, // Galamoth
    203, // Minotaurus
    206, // Werewolf
    243, // Slogra
    253, // Doppleganger10
    254, // Gaibon
    267, // Akmodan II
    273, // Darkwing Bat
    280, // Karasuman
    287, // Scylla
    295, // Granfaloon
    296, // Granfaloon (core)
    300, // Hippogryph
    307, // Richter Belmont
    324, // Beezelbub
    328, // Fake Trevor
    334, // Fake Grant
    337, // Fake Sypha
    342, // Succubus
    351, // Shaft
    356, // Death
    361, // Death (second form)
    363, // Cerberos
    366, // Medusa
    370, // The Creature
    372, // Doppleganger40
    379, // Dracula (final)
    386, // Minotaur (inverted castle)
    389, // Werewolf (inverted castle)
};

static s16 s_BaseHp[LEN(s_Bosses)]; // the table's own values, read once
static bool s_HpRead, s_HpDoubled;
static bool s_BossHere; // a living boss is in this room

// Aggro, per stage slot: the wrapped update, the target, when it was picked
static PfnEntityUpdate s_Update[STAGE_SLOTS];
static u8 s_TargetPartner[STAGE_SLOTS];
static u16 s_Picked[STAGE_SLOTS];
static u32 s_Seed = 0x2545F491; // own generator: the game's rand() must stay untouched
static u16 s_Frame;
static u16 s_Switches; // target switches so far (presence.aggroSwitches: tests)

bool IsBossEnemy(u16 enemyId) {
    s32 i;

    for (i = 0; i < LEN(s_Bosses); i++) {
        if (s_Bosses[i] == enemyId) {
            return true;
        }
    }
    return false;
}

static u32 Roll(void) {
    s_Seed = s_Seed * 1103515245 + 12345;
    return (s_Seed >> 16) & 0xFF;
}

static bool PartnerLinked(void) {
    return g_CoopLink.partnerAge < 60 && (g_CoopLink.partner.flags & PRESENCE_IN_PLAY);
}

static bool PartnerFighting(void) {
    const CoopPresence* p = &g_CoopLink.partner;

    return PartnerLinked() && !(p->flags & (PRESENCE_DEAD | PRESENCE_BUSY)) && p->stage == g_StageId &&
           p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top;
}

// --- 2x HP (D25)

static void UpdateHp(void) {
    EnemyDef* defs = g_api.enemyDefs;
    bool want = g_CoopLink.partnerAge < 600; // a partner's game has been heard from (10 s)
    s32 i, hp;

    if (!defs) {
        return;
    }
    if (!s_HpRead) {
        for (i = 0; i < LEN(s_Bosses); i++) {
            s_BaseHp[i] = defs[s_Bosses[i]].hitPoints;
        }
        s_HpRead = true;
    }
    if (want == s_HpDoubled || s_BossHere) { // never mid-fight
        return;
    }
    for (i = 0; i < LEN(s_Bosses); i++) {
        hp = s_BaseHp[i] * (want ? 2 : 1);
        defs[s_Bosses[i]].hitPoints = hp > HP_MAX ? HP_MAX : hp;
    }
    s_HpDoubled = want;
}

// --- aggro (D47)

static void PickTarget(s32 slot, Entity* e) {
    u32 chance;

    if (!PartnerFighting()) {
        s_TargetPartner[slot] = false;
        return;
    }
    if (g_CoopLink.control & CONTROL_NO_AGGRO) {
        s_TargetPartner[slot] = false;
        return;
    }
    // "After each attack" (D47), approximated by time: bosses' state machines differ too much
    // to find their attacks generically. (A step change was tried first: the Doppleganger's
    // step rarely changes, so it hardly ever switched.)
    if ((u16)(s_Frame - s_Picked[slot]) >= AGGRO_PERIOD) {
        chance = (g_CoopLink.control >> CONTROL_AGGRO_SHIFT) & 0xFF;
        if (Roll() < (chance ? chance : AGGRO_SWITCH)) {
            s_TargetPartner[slot] = !s_TargetPartner[slot];
            s_Switches++;
        }
        s_Picked[slot] = s_Frame;
    }
}

static void BossUpdateWrap(Entity* e) {
    s32 slot = e - &g_Entities[STAGE_ENTITY_START];
    PfnEntityUpdate update = s_Update[slot];
    const CoopPresence* p = &g_CoopLink.partner;
    s16 x, y, fakeX, fakeY;
    u16 facing;
    s32 playerX, playerY;

    PickTarget(slot, e);
    if (!s_TargetPartner[slot]) {
        update(e);
    } else {
        x = PLAYER.posX.i.hi;
        y = PLAYER.posY.i.hi;
        facing = PLAYER.facingLeft;
        playerX = g_PlayerX;
        playerY = g_PlayerY;
        fakeX = p->x - g_Tilemap.scrollX.i.hi;
        fakeY = p->y - g_Tilemap.scrollY.i.hi;
        PLAYER.posX.i.hi = fakeX;
        PLAYER.posY.i.hi = fakeY;
        PLAYER.facingLeft = (p->flipX & 2) != 0;
        g_PlayerX = p->x;
        g_PlayerY = p->y;
        update(e);
        // Put the player back. If the boss moved "the player" (a grab), move the real one
        // by as much.
        PLAYER.posX.i.hi = x + (PLAYER.posX.i.hi - fakeX);
        PLAYER.posY.i.hi = y + (PLAYER.posY.i.hi - fakeY);
        PLAYER.facingLeft = facing;
        g_PlayerX = playerX;
        g_PlayerY = playerY;
    }
    if (e->pfnUpdate != BossUpdateWrap && e->pfnUpdate) { // the boss switched its own update
        s_Update[slot] = e->pfnUpdate;
        e->pfnUpdate = BossUpdateWrap;
    }
}

// The update a snapshot must carry: the guest has no wrapper state for this slot.
PfnEntityUpdate BossRealUpdate(const Entity* e) {
    if (e->pfnUpdate == BossUpdateWrap) {
        return s_Update[e - &g_Entities[STAGE_ENTITY_START]];
    }
    return e->pfnUpdate;
}

static void ScanBosses(void) {
    Entity* e;
    s32 i;
    bool here = false;
    bool wrap = SharedRole() != ROLE_GUEST; // a guest's bosses are copies: nothing runs them

    for (i = 0; i < STAGE_SLOTS; i++) {
        e = &g_Entities[STAGE_ENTITY_START + i];
        if (!e->entityId || !e->pfnUpdate || !IsBossEnemy(e->enemyId)) {
            continue;
        }
        if (e->hitPoints > 0 && !(e->flags & FLAG_DEAD)) {
            here = true;
        }
        if (wrap && e->pfnUpdate != BossUpdateWrap) {
            s_Update[i] = e->pfnUpdate;
            e->pfnUpdate = BossUpdateWrap;
            s_TargetPartner[i] = false;
            s_Picked[i] = s_Frame;
        } else if (!wrap && e->pfnUpdate == BossUpdateWrap) {
            e->pfnUpdate = s_Update[i];
        }
    }
    s_BossHere = here;
}

void BossUpdate(void) {
    s_Frame++;
    if (g_GameState != Game_Play || g_GameStep != Play_Default) {
        s_BossHere = false;
        return;
    }
    ScanBosses();
    UpdateHp();
}

bool BossHere(void) { return s_BossHere; }

u16 BossSwitches(void) { return s_Switches; }
