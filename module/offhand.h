// Off-hand weapons for Richter and Maria (design/M8b §4.1, offhand.c).
#ifndef OFFHAND_H
#define OFFHAND_H

void OffhandUpdate(void); // once per frame, before UpdateGame
bool OffhandLoading(void); // a weapon is being loaded (the CD is the module's)

void OffhandKeepSheet(s32 hand); // Maria: a hand weapon's sheet just loaded: keep a copy (D106)
void OffhandPlaceSheet(void);      // ...and put the ○ hand's copy beside her guardians
// A weapon entity's bank (0x10-0x13), palette and hand as its overlay set them (weapons.c)
bool OffhandOriginal(Entity* e, s32* set, u16* palette, s32* hand);

#endif
