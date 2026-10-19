// The partner, drawn as a tinted copy of their player sprite (design/M1-link-presence.md, part 4).
#ifndef PUPPET_H
#define PUPPET_H
#include "link.h"

#define PARTNER_STALE_FRAMES 30 // no host update for this long: hide the partner

void DrawPuppet(const CoopPresence* p);

#endif
