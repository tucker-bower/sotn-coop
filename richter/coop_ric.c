// Our Richter's co-op additions (design/M8b): his power grows like Alucard's.
#include "ric.h"

// Tuning knobs (M8b §5: the balance runs set them).
#define WHIP_STR_PCT 100   // the whip gains this % of STR (Alucard's weapons gain all of it)
#define SUBWPN_INT_DIV 50  // subweapons and crashes: × (1 + INT / this)
#define FIRE_WHIP_PCT 125  // Fire of Bat: the whip burns, for this % of its damage

#define SUBWPN_WHIP 14       // gen/subweapons.h: the whip (32)
#define SUBWPN_FLAME_WHIP 15 // △ with no subweapon (64)

// RicSetSubweaponParams's attack, for every attack Richter makes (the whip is a "subweapon").
s32 CoopRicAttack(Entity* entity, s32 id, s32 attack) {
    if (id == SUBWPN_WHIP || id == SUBWPN_FLAME_WHIP) {
        attack += g_Status.statsTotal[STAT_STR] * WHIP_STR_PCT / 100;
        if (id == SUBWPN_WHIP && COOP_CAN(RELIC_FIRE_OF_BAT)) {
            attack = attack * FIRE_WHIP_PCT / 100;
            entity->attackElement |= ELEMENT_FIRE;
        }
    } else if (attack) {
        attack += attack * g_Status.statsTotal[STAT_INT] / SUBWPN_INT_DIV;
    }
    return attack;
}
