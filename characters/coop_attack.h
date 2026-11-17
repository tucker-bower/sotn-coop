// Richter's and Maria's own attack under "Alucard's stats" (M8b §5, issue 114): the tuning knobs
// their overlays (richter-ps1/coop_ric.c, maria-dx/coop_maria.c) and the module's status page
// (module/offhand.c, #204) share.
#ifndef COOP_ATTACK_H
#define COOP_ATTACK_H

#define WHIP_ATTACK 32     // the whip's own attack (src/ric gen/subweapons.h)
#define WHIP_BASE_PCT 20   // issue 114: his whip's own attack, so his damage a second is Alucard's
#define WHIP_STR_PCT 100   // the whip gains this % of STR (Alucard's weapons gain all of it)
#define FIRE_WHIP_PCT 125  // Fire of Bat: the whip burns, for this % of its damage
#define ECHO_WHIP_PCT 125  // Force of Echo: the whip's echo, this % of its damage (it's holy already)

#define OWL_ATTACK 12      // the owl's own attack (src/maria/pl_blueprints.c EntityMariaOwl)
#define BASIC_BASE_PCT 50  // issue 114: her attack's own value, so her damage a second is Alucard's
#define BASIC_STR_PCT 100  // her own attack gains this % of STR
#define FIRE_PCT 125       // Fire of Bat: her attack burns, for this % of its damage
#define ECHO_PCT 125       // Force of Echo: her attack's echo, this % of its damage

#endif
