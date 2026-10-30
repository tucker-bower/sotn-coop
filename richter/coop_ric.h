// Our Richter's link to the co-op module (design/M8b): included in every src/ric file of our
// build (Makefile: -include). The changes in src/ric are marked COOP_RIC.
#ifndef COOP_RIC_H
#define COOP_RIC_H

// The module's per-player settings, mirrored from the mailbox every frame (module/coop_api.h:
// a word in its fixed table, coop_player.ld).
extern unsigned int g_CoopOptions; // included before game.h: no u32 yet
#define OPT_SHORTCUTS 1 // one-button moves: L2 high jump, R2 blade dash (M8b §3.2)

// A move Alucard's relic unlocks (M8b §3): the relic is found and switched on.
#define COOP_CAN(relic) (g_Status.relics[relic] & RELIC_FLAG_ACTIVE)
struct Entity;
int CoopRicAttack(struct Entity* entity, int id, int attack); // coop_ric.c
#define COOP_SHORTCUT(pad) ((g_CoopOptions & OPT_SHORTCUTS) && (g_Player.padTapped & (pad)))

// Extra jumps (D122): each of the Leap Stone and the Gravity Boots gives one jump in the air, so
// Richter and Maria reach what Alucard reaches with the same relics (his double jump and super
// jump). g_CoopAirJumps: Richter's, how many he's used since the ground; Maria's, bits (src/maria
// pl_collision.c). Both coop_ric.c / coop_maria.c, refilled on the ground in RicMain / MarMain.
extern int g_CoopAirJumps;
#define COOP_AIR_JUMPS ((COOP_CAN(RELIC_LEAP_STONE) != 0) + (COOP_CAN(RELIC_GRAVITY_BOOTS) != 0))
#define COOP_AIR_JUMP_LEFT (g_CoopAirJumps < COOP_AIR_JUMPS)

// The partner's builds (design/M13 step 3: COOPRICP.BIN, MARIAP.BIN, built with COOP_PARTNER):
// a second Richter or Maria beside player 1. What its code writes to or reads from VRAM is in the
// second bank (richter/coop_partner.c), never player 1's graphics.
#ifdef COOP_PARTNER
#define LoadImage CoopPartnerLoadImage
#define StoreImage CoopPartnerStoreImage
#endif

#endif
