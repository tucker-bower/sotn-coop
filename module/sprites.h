#ifndef SPRITES_H
#define SPRITES_H

void SpritesCapture(void); // after RenderEntities: this player's sprites, for the partner
void SpritesPlace(void);   // before RenderEntities: the partner's, into free slots
void SpritesRemove(void);  // after RenderEntities: out again
void PrimsCapture(void);   // after the frame's updates: this player's primitives
void PrimsPlace(void);     // before the primitives are drawn: the partner's

#endif
