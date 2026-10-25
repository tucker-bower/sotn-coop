// Our Maria's link to the co-op module (design/M8b): included in every file of our build
// (Makefile: -include). The changes in src/maria are marked COOP_MARIA. Same rules as our
// Richter's (richter/coop_ric.h).
#ifndef COOP_MARIA_H
#define COOP_MARIA_H

#include "coop_ric.h"

struct Entity;
int CoopMarAttack(struct Entity* entity, int subweapon, int attack); // coop_maria.c
#define COOP_MAR_BASIC (-1) // CoopMarAttack: her own attack, not a guardian

#endif
