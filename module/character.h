// Playable Richter and Maria (design/M8, character.c).
#ifndef CHARACTER_H
#define CHARACTER_H

#include "link.h"

void CharacterFrame(void);   // once per frame, before UpdateGame
void CharacterApply(void);   // right before a load picks the player's files
u32 CharacterLoaded(void);   // CHAR_* of this game's player
const CharBlob* CharacterBlob(u32 character); // the launcher's blob for that character, or NULL
void CharacterBeforePrims(void); // the frame's primitives are about to be drawn
void CharacterCurePoison(void); // Richter's and Maria's (character.c)
// Co-op Richter and Maria: levels, Alucard's stats, relic moves, off-hand weapons, familiars and
// the rest are theirs. Other mods' characters play as their mod built them.
#define CHAR_COOP(c) ((c) == CHAR_RICHTER || (c) == CHAR_MARIA)
// Co-op or Ultimate Maria: Maria's layout (her guardians' reload hook, her sheet). Saturn Maria is a
// fork of Richter's code, with his layout; her blob is CHAR_SAT_MARIA's.
#define CHAR_IS_MARIA(c) ((c) == CHAR_MARIA || (c) == CHAR_ULT_MARIA)
// Both players in the same world: the castle, or both in the prologue. Any characters together.
#define SAME_WORLD(p) (((p)->stage == STAGE_ST0) == (g_StageId == STAGE_ST0))

#endif
