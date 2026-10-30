// Our Maria's co-op additions (design/M8b): her power grows like Alucard's.
#include "maria.h"

// Tuning knobs (M8b §5), as for Richter (richter/coop_ric.c).
#define BASIC_STR_PCT 100  // her own attack gains this % of STR
#define GUARDIAN_INT_DIV 50 // guardians and their crashes: × (1 + INT / this)
#define FIRE_PCT 125       // Fire of Bat: her attack burns, for this % of its damage
#define ECHO_PCT 125       // Force of Echo: her attack's echo, this % of its damage
#define GUARDIAN_TURTLE 3        // src/maria/gen/subweapons.h
#define GUARDIAN_TURTLE_CRASH 16

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

// Her init as the partner (maria/maria_partner.ld's trailer: the module calls it). Her own
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

s32 CoopMarAttack(Entity* entity, s32 subweapon, s32 attack) {
    if (subweapon == COOP_MAR_BASIC) {
        attack += g_Status.statsTotal[STAT_STR] * BASIC_STR_PCT / 100;
        if (COOP_CAN(RELIC_FIRE_OF_BAT)) {
            attack = attack * FIRE_PCT / 100;
            entity->attackElement |= ELEMENT_FIRE;
        }
        if (COOP_CAN(RELIC_FORCE_OF_ECHO)) {
            attack = attack * ECHO_PCT / 100;
        }
    } else if (attack) {
        attack += attack * g_Status.statsTotal[STAT_INT] / GUARDIAN_INT_DIV;
    }
    // Gas Cloud: the turtle and its crash poison (M8b §3).
    if ((subweapon == GUARDIAN_TURTLE || subweapon == GUARDIAN_TURTLE_CRASH) && COOP_CAN(RELIC_GAS_CLOUD)) {
        entity->attackElement |= ELEMENT_POISON;
    }
    return attack;
}
