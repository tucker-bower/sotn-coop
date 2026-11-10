// Playable Richter and Maria (design/M8, character.c).
#ifndef CHARACTER_H
#define CHARACTER_H

#include "link.h"

void CharacterFrame(void);   // once per frame, before UpdateGame
void CharacterApply(void);   // right before a load picks the player's files
u32 CharacterLoaded(void);   // CHAR_* of this game's player
const CharBlob* CharacterBlob(u32 character); // the launcher's blob for that character, or NULL
void CharacterBeforePrims(void); // the frame's primitives are about to be drawn
// Ultimate Richter's coat (a RIC2 file: his palettes and arm art), into the game's palettes and
// VRAM, or into VRAM's second bank for a partner who wears it
void CharacterRicCoat(const u8* file, bool partner);
void CharacterCurePoison(void); // Richter's and Maria's (character.c)
// Co-op Richter and Maria: levels, Alucard's stats, relic moves, off-hand weapons, familiars and
// the rest are theirs. Other mods' characters play as their mod built them.
#define CHAR_COOP(c) ((c) == CHAR_RICHTER || (c) == CHAR_MARIA)
// Co-op or Ultimate Maria: Maria's layout (her guardians' reload hook, her sheet). Saturn Maria is a
// fork of Richter's code, with his layout; her blob is CHAR_SAT_MARIA's.
#define CHAR_IS_MARIA(c) ((c) == CHAR_MARIA || (c) == CHAR_ULT_MARIA)
// Both players in the same world: the castle, or both in the prologue. Any characters together.
// A pose Maria's frame table doesn't have (a scene set one of Alucard's: issue 209) reads past its
// end, and her sprite upload went over the screen: drawn as her stand instead.
#define MAR_FRAMES 124       // maria_spr: frames 1-123 (src/maria/gen/maria_spr.h)
#define MAR_FRAME_STAND 68   // mar_anim_stand_relax's first (src/maria/pl_anims.c)
#define ANIMSET_MARIA 0x8010 // ANIMSET_OVL(0x10): her body
#define MAR_SAFE_FRAME(c, e) \
    (CHAR_IS_MARIA(c) && (u16)(e)->animSet == ANIMSET_MARIA && ((e)->animCurFrame & 0x7FFF) >= MAR_FRAMES \
         ? MAR_FRAME_STAND | ((e)->animCurFrame & 0x8000) : (e)->animCurFrame)
#define SAME_WORLD(p) (((p)->stage == STAGE_ST0) == (g_StageId == STAGE_ST0))

#endif
