// Our Maria's co-op additions (design/M8b): her power grows like Alucard's.
#include "maria.h"

// Tuning knobs (M8b §5), as for Richter (richter/coop_ric.c).
#define BASIC_STR_PCT 100  // her own attack gains this % of STR
#define GUARDIAN_INT_DIV 50 // guardians and their crashes: × (1 + INT / this)
#define FIRE_PCT 125       // Fire of Bat: her attack burns, for this % of its damage

// Her frame tables, at a fixed place (maria.ld: 0x8013C1F0), for another character's game to
// draw her from its copy (module/puppet.c).
extern s16* maria_spr[];
s16** CoopMarBanks[1] = {maria_spr};

s32 CoopMarAttack(Entity* entity, s32 subweapon, s32 attack) {
    if (subweapon == COOP_MAR_BASIC) {
        attack += g_Status.statsTotal[STAT_STR] * BASIC_STR_PCT / 100;
        if (COOP_CAN(RELIC_FIRE_OF_BAT)) {
            attack = attack * FIRE_PCT / 100;
            entity->attackElement |= ELEMENT_FIRE;
        }
    } else if (attack) {
        attack += attack * g_Status.statsTotal[STAT_INT] / GUARDIAN_INT_DIV;
    }
    return attack;
}
