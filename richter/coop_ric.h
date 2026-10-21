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

#endif
