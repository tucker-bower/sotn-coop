// Our Maria's co-op additions (design/M8b): her power grows like Alucard's.
#include "maria.h"

// Tuning knobs (M8b §5), as for Richter (characters/richter-ps1/coop_ric.c).
#define BASIC_BASE_PCT 50  // issue 114: her attack's own value, so her damage a second is Alucard's
#define BASIC_STR_PCT 100  // her own attack gains this % of STR
#define GUARDIAN_INT_DIV 50 // guardians and their crashes: × (1 + INT / this)
#define FIRE_PCT 125       // Fire of Bat: her attack burns, for this % of its damage
#define ECHO_PCT 125       // Force of Echo: her attack's echo, this % of its damage

// Her frame tables, at a fixed place (maria.ld: 0x8013C1F0), for another character's game to
// draw her from its copy (module/puppet.c).
extern s16* maria_spr[];
s16** CoopMarBanks[1] = {maria_spr};

// ...and, next (0x8013C1F4), her guardians' graphics upload: the module calls it when a hand
// weapon's graphics have loaded over them (module/character.c).
void MARIA_Load(void);
void (*CoopMarHooks[1])(void) = {MARIA_Load};

int g_CoopAirJumps; // D122: jumps in the air used since the ground (coop_ric.h)

#ifdef COOP_PARTNER
// The partner's Maria (design/M13 step 3): her palettes, apart from the game's (coop_maria.h).
u16 g_CoopPartnerClut[3][0x1000];

// Her init as the partner (characters/maria-dx/maria_partner.ld's trailer: the module calls it). Her own
// (mariapsp-forpsx's MarPsxInit) also patches DRA's HUD and sound data, once: in another
// character's game that would be player 1's; here only her load (its uploads go to the second
// bank) and the damage functions her attacks look up.
void MarInit(s16 initParam);
void CoopMarPartnerInit(u16 initParam) {
    MARIA_Load();
    g_api.CalcDealDamageMaria = g_api.func_800FD664;
    g_api.CalcPlayerDamageMaria = g_api.CalcPlayerDamage;
    MarInit(initParam);
}
#endif

// Gear on her guardians, as DRA gives Alucard's sub-weapons (src/dra/5D5BC.c, func_800FE3C4), with
// the castle's gear effects on (#202): a Heart Broach halves their heart cost (a third with two),
// Brilliant Mail adds 10 to their attack (src/maria/pl_subweapons.c: each guardian's own value,
// before CoopMarAttack). She has no holy water, so no Staurolite.
#define GEAR_ON (!(g_CoopOptions & OPT_NO_GEAR_EFFECTS))

s32 CoopMarHeartCost(s32 cost) {
    s32 n = GEAR_ON ? g_api.CheckEquipmentItemCount(ITEM_HEART_BROACH, EQUIP_ACCESSORY) : 0;

    cost = n == 1 ? cost / 2 : n == 2 ? cost / 3 : cost;
    return cost < 1 ? 1 : cost;
}

s32 CoopMarGuardianGear(s32 attack) {
    if (attack && GEAR_ON && g_api.CheckEquipmentItemCount(ITEM_BRILLIANT_MAIL, EQUIP_ARMOR)) {
        attack += 10;
    }
    return attack;
}

// Her attacks under "Alucard's stats" (#238, Tucker): her own (the owl) and her body's (slide
// kick, blade dash, high jump: MarSetSubweaponParams, with their PL_W_ id) grow with STR, the body's
// in proportion to the owl's, as Richter's body moves to his whip's; her guardians' (every attack in
// src/maria/pl_subweapons.c, which sets g_CoopMarGuardian) with INT.
#define OWL_ATTACK 12 // the owl's own attack (src/maria/pl_blueprints.c EntityMariaOwl)
int g_CoopMarGuardian;

s32 CoopMarAttack(Entity* entity, s32 subweapon, s32 attack) {
    s32 guardian = g_CoopMarGuardian;

    if (g_CoopOptions & OPT_NO_ALUCARD_STATS) {
        return attack; // the castle's rules: her attacks as in her own game
    }
    if (g_Status.D_80097BF8 & 1) {
        attack /= 2; // poisoned (module/character.c)
    }
    if (guardian) {
        if (attack) {
            attack += attack * g_Status.statsTotal[STAT_INT] / GUARDIAN_INT_DIV;
        }
        // Gas Cloud: the turtle and its crash poison (M8b §3).
        if (guardian == COOP_MAR_TURTLE && COOP_CAN(RELIC_GAS_CLOUD)) {
            entity->attackElement |= ELEMENT_POISON;
        }
    } else if (subweapon == COOP_MAR_BASIC) {
        attack = attack * BASIC_BASE_PCT / 100 + g_Status.statsTotal[STAT_STR] * BASIC_STR_PCT / 100;
        if (COOP_CAN(RELIC_FIRE_OF_BAT)) {
            attack = attack * FIRE_PCT / 100;
            entity->attackElement |= ELEMENT_FIRE;
        }
        if (COOP_CAN(RELIC_FORCE_OF_ECHO)) {
            attack = attack * ECHO_PCT / 100;
        }
    } else if (attack) {
        attack = (OWL_ATTACK * BASIC_BASE_PCT / 100 + g_Status.statsTotal[STAT_STR] * BASIC_STR_PCT / 100) * attack /
                 OWL_ATTACK;
    }
    return attack;
}
