// Playable Richter and Maria (design/M8, character.c).
#ifndef CHARACTER_H
#define CHARACTER_H

void CharacterFrame(void);   // once per frame, before UpdateGame
void CharacterApply(void);   // right before a load picks the player's files
u32 CharacterLoaded(void);   // CHAR_* of this game's player
// Both players in the same world: the castle, or both in the prologue. Any characters together.
#define SAME_WORLD(p) (((p)->stage == STAGE_ST0) == (g_StageId == STAGE_ST0))

#endif
