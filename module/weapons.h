#ifndef WEAPONS_H
#define WEAPONS_H

void WeaponLoaded(s32 hand);                     // the CD just loaded that hand's weapon
void WeaponKeepClut(s32 hand, const u16* clut);  // Richter, Maria: its palettes, as they loaded
void WeaponsUpdate(void);                        // once per frame
void WeaponsDraw(void);                          // after RenderEntities: the partner's swings
bool WeaponSprite(Entity* e, CoopSprite* s);     // e is a hand weapon's sprite: s as sent

#endif
