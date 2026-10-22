// Off-hand weapons for Richter and Maria (design/M8b §4.1, offhand.c).
#ifndef OFFHAND_H
#define OFFHAND_H

void OffhandUpdate(void); // once per frame, before UpdateGame
bool OffhandLoading(void); // a weapon is being loaded (the CD is the module's)

#endif
