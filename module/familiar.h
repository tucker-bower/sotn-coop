// M13 step 4: the partner's familiar (familiar.c).
#ifndef FAMILIAR_H
#define FAMILIAR_H

void FamiliarUpdate(void);           // once per frame: this game's copy
void FamiliarDraw(s16 dx, s16 dy);   // in the partner's drawing pass (partner.c)
void FamiliarReload(void);           // the second bank was reloaded: the partner's copy again

// Co-op Maria's own familiar (issue 208): its graphics live in VRAM's second bank, since hers
// share its page in the first.
void FamiliarToBank(void);   // its graphics just loaded: copy them there (character.c)
void FamiliarHideOwn(void);  // around RenderEntities: its sprites out of the game's pass...
void FamiliarDrawOwn(void);  // ...and drawn in a pass of their own, from the bank
void FamiliarOwnPrims(void); // before RenderPrimitives: its primitives read the bank too...
void FamiliarOwnPrimsBack(void); // ...and after, as they were

#endif
