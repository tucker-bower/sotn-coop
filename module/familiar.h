// M13 step 4: the partner's familiar (familiar.c).
#ifndef FAMILIAR_H
#define FAMILIAR_H

void FamiliarUpdate(void);           // once per frame: this game's copy
void FamiliarDraw(s16 dx, s16 dy);   // in the partner's drawing pass (partner.c)
void FamiliarReload(void);           // the second bank was reloaded: the partner's copy again

#endif
