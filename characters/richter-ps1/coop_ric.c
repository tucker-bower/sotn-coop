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
#define WHIP_BASE_PCT 20   // issue 114: his whip's own attack, so his damage a second is Alucard's
#define WHIP_STR_PCT 100   // the whip gains this % of STR (Alucard's weapons gain all of it)
#define SUBWPN_INT_DIV 50  // subweapons and crashes: × (1 + INT / this)
#define FIRE_WHIP_PCT 125  // Fire of Bat: the whip burns, for this % of its damage
#define ECHO_WHIP_PCT 125  // Force of Echo: the whip's echo, this % of its damage (it's holy already)

#define SUBWPN_WHIP 14       // gen/subweapons.h: the whip (32)
#define SUBWPN_FLAME_WHIP 15 // △ with no subweapon (64)
#define SUBWPN_HOLY_WATER 3  // and its flames (11) and crash, Hydro Storm (16)
#define SUBWPN_HOLY_FLAMES 11
#define SUBWPN_HYDRO_STORM 16
// His body's attacks (issue 190): Blade Dash (it uses the Bible crash beam's entry: told apart by
// its entity), the slide, the slide kick and the high jump. They do the whip's damage times their
// own attack over the whip's, his own game's ratios (Blade Dash and the high jump 2.5 times the
// whip), so they grow with STR as it does, not INT.
#define SUBWPN_BIBLE_BEAM 17
#define SUBWPN_SLIDE 18
#define SUBWPN_HIGH_JUMP 22
#define SUBWPN_SLIDE_KICK 23
#define BODY_ATTACK(e, id) \
    ((id) == SUBWPN_SLIDE || (id) == SUBWPN_HIGH_JUMP || (id) == SUBWPN_SLIDE_KICK || \
     ((id) == SUBWPN_BIBLE_BEAM && (e)->entityId == E_BLADE_DASH))
#define WHIP_ATTACK 32 // the whip's own attack (gen/subweapons.h)

// RicSetSubweaponParams's attack, for every attack Richter makes (the whip is a "subweapon").
int g_CoopAirJumps; // D122: jumps in the air used since the ground (coop_ric.h)

s32 CoopRicAttack(Entity* entity, s32 id, s32 attack) {
    if (g_CoopOptions & OPT_NO_ALUCARD_STATS) {
        return attack; // the castle's rules: his attacks as in his own game
    }
    if (g_Status.D_80097BF8 & 1) {
        attack /= 2; // poisoned (module/character.c)
    }
    if (id == SUBWPN_WHIP || id == SUBWPN_FLAME_WHIP) {
        attack = attack * WHIP_BASE_PCT / 100 + g_Status.statsTotal[STAT_STR] * WHIP_STR_PCT / 100;
        if (id == SUBWPN_WHIP && COOP_CAN(RELIC_FIRE_OF_BAT)) {
            attack = attack * FIRE_WHIP_PCT / 100;
            entity->attackElement |= ELEMENT_FIRE;
        }
        if (COOP_CAN(RELIC_FORCE_OF_ECHO)) {
            attack = attack * ECHO_WHIP_PCT / 100;
        }
    } else if (BODY_ATTACK(entity, id)) {
        attack = (WHIP_ATTACK * WHIP_BASE_PCT / 100 + g_Status.statsTotal[STAT_STR] * WHIP_STR_PCT / 100) * attack /
                 WHIP_ATTACK;
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
