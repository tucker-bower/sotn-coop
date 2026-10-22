// Our Richter's co-op additions (design/M8b): his power grows like Alucard's.
#include "ric.h"

// Richter's frame tables (his animSets 0x8010-0x8013), at a fixed place in the file (ric.ld:
// right after richter_sprites, 0x8013C334), so another character's game can draw him from its
// copy of this file (module/puppet.c).
extern s16* spritebank0[];
extern s16* spritebank1[];
extern s16* spritebank2[];
extern s16* spritebank3[];
s16** CoopRicBanks[4] = {spritebank0, spritebank1, spritebank2, spritebank3};

// Tuning knobs (M8b §5: the balance runs set them).
#define WHIP_STR_PCT 100   // the whip gains this % of STR (Alucard's weapons gain all of it)
#define SUBWPN_INT_DIV 50  // subweapons and crashes: × (1 + INT / this)
#define FIRE_WHIP_PCT 125  // Fire of Bat: the whip burns, for this % of its damage
#define ECHO_WHIP_PCT 125  // Force of Echo: the whip's echo, this % of its damage (it's holy already)

#define SUBWPN_WHIP 14       // gen/subweapons.h: the whip (32)
#define SUBWPN_FLAME_WHIP 15 // △ with no subweapon (64)
#define SUBWPN_HOLY_WATER 3  // and its flames (11) and crash, Hydro Storm (16)
#define SUBWPN_HOLY_FLAMES 11
#define SUBWPN_HYDRO_STORM 16

// RicSetSubweaponParams's attack, for every attack Richter makes (the whip is a "subweapon").
s32 CoopRicAttack(Entity* entity, s32 id, s32 attack) {
    if (id == SUBWPN_WHIP || id == SUBWPN_FLAME_WHIP) {
        attack += g_Status.statsTotal[STAT_STR] * WHIP_STR_PCT / 100;
        if (id == SUBWPN_WHIP && COOP_CAN(RELIC_FIRE_OF_BAT)) {
            attack = attack * FIRE_WHIP_PCT / 100;
            entity->attackElement |= ELEMENT_FIRE;
        }
        if (COOP_CAN(RELIC_FORCE_OF_ECHO)) {
            attack = attack * ECHO_WHIP_PCT / 100;
        }
    } else if (attack) {
        attack += attack * g_Status.statsTotal[STAT_INT] / SUBWPN_INT_DIV;
    }
    // Gas Cloud: holy water and its crash poison (M8b §3).
    if ((id == SUBWPN_HOLY_WATER || id == SUBWPN_HOLY_FLAMES || id == SUBWPN_HYDRO_STORM) &&
        COOP_CAN(RELIC_GAS_CLOUD)) {
        entity->attackElement |= ELEMENT_POISON;
    }
    return attack;
}
