// Alucard's spell shortcuts (design/M8b §3.2): a flick of the right stick casts the spell the
// player chose for that direction, if Alucard knows it. Off unless the player turned the
// shortcuts on (OPT_SHORTCUTS), as for Richter's and Maria's.
//
// The flick plays the spell's own button sequence into his pad, one step a frame, so the
// game's own checks (src/dra/704D0.c) decide: his pose, his MP, and learning it. A modern pad's
// right stick isn't a PlayStation button: the host sends it as CoopLink.padExtra (PADX_*), with
// the inputs, so each game stays deterministic.
#define COOP_MODULE
#include <game.h>
#include "coop_api.h"
#include "link.h"
#include "character.h"
#include "spells.h"

// One step of a sequence: directions relative to where he faces, and the attack button.
#define K_U 1
#define K_D 2
#define K_F 4
#define K_B 8
#define K_ATK 16
typedef struct {
    u8 buttons;
    u8 frames; // held this long
} Step;

// The sequences, as 704D0.c checks them (each step's timer allows 20 frames: one is enough).
static const Step s_DarkMetamorphosis[] = {{K_B, 1}, {K_U | K_B, 1}, {K_U, 1}, {K_U | K_F, 1}, {K_F, 1}, {K_ATK, 1}};
static const Step s_SummonSpirit[] = {{K_B, 1}, {K_F, 1}, {K_U, 1}, {K_D, 4}, {K_D | K_ATK, 1}};
static const Step s_Hellfire[] = {{K_U, 1}, {K_D, 1}, {K_D | K_F, 1}, {K_F, 1}, {K_ATK, 1}};
// Up held for 32 frames, then a half circle forward to down, crouching.
static const Step s_TetraSpirit[] = {{K_U, 34}, {K_U | K_F, 1}, {K_F, 1}, {K_D | K_F, 1}, {K_D, 4}, {K_D | K_ATK, 1}};
static const Step s_SoulSteal[] = {{K_B, 1}, {K_F, 1}, {K_D | K_F, 1}, {K_D, 1}, {K_D | K_B, 1},
                                   {K_B, 1}, {K_F, 1}, {K_ATK, 1}};
// Down to up-forward, up held for 64 frames, let go, then down and attack, crouching.
static const Step s_SwordBrothers[] = {{K_D, 1}, {K_D | K_F, 1}, {K_F, 1}, {K_U | K_F, 1}, {K_U, 66},
                                       {0, 1}, {K_D, 4}, {K_D | K_ATK, 1}};

static const struct {
    const Step* steps;
    u8 count;
} s_Spells[NUM_SPELLS] = {
    [SPELL_DARK_METAMORPHOSIS] = {s_DarkMetamorphosis, LEN(s_DarkMetamorphosis)},
    [SPELL_SUMMON_SPIRIT] = {s_SummonSpirit, LEN(s_SummonSpirit)},
    [SPELL_HELLFIRE] = {s_Hellfire, LEN(s_Hellfire)},
    [SPELL_TETRA_SPIRIT] = {s_TetraSpirit, LEN(s_TetraSpirit)},
    [SPELL_SOUL_STEAL] = {s_SoulSteal, LEN(s_SoulSteal)},
    [SPELL_SWORD_BROTHERS] = {s_SwordBrothers, LEN(s_SwordBrothers)},
    // Wolf Charge and Wing Smash need the wolf or the bat: not on the stick.
};

extern SpellDef g_SpellDefs[]; // DRA

static const Step* s_Steps; // the sequence playing, or NULL
static u8 s_Count, s_Step, s_Held;
static bool s_FacingLeft;   // when it started: "forward" stays the same throughout
static u16 s_PrevPressed;   // what the sequence pressed last frame
static u32 s_PrevExtra;

// The spell the player put on that direction (OPT_SPELL_*), if Alucard can cast it now.
static s32 Chosen(u32 dir) {
    s32 spell = (g_CoopLink.options >> (OPT_SPELL_SHIFT + dir * 4) & 0xF) - 1;

    if (!(g_CoopLink.options & OPT_SHORTCUTS) || spell < 0 || spell >= NUM_SPELLS || !s_Spells[spell].steps ||
        !(g_Status.spellsLearnt & (1 << spell)) || g_Status.mp < g_SpellDefs[spell].mpUsage ||
        (spell == SPELL_SWORD_BROTHERS && g_Servant != FAM_ACTIVE_SWORD)) { // as 704D0.c's rule
        return -1;
    }
    return spell;
}

static u16 Buttons(u8 b) {
    u16 pressed = 0;
    if (b & K_U) {
        pressed |= PAD_UP;
    }
    if (b & K_D) {
        pressed |= PAD_DOWN;
    }
    if (b & K_F) {
        pressed |= s_FacingLeft ? PAD_LEFT : PAD_RIGHT;
    }
    if (b & K_B) {
        pressed |= s_FacingLeft ? PAD_RIGHT : PAD_LEFT;
    }
    if (b & K_ATK) {
        pressed |= PAD_SQUARE;
    }
    return pressed;
}

// Once per frame, after the pads are read and before UpdateGame.
void SpellsUpdate(void) {
    u32 extra = g_CoopLink.padExtra, flicked = extra & ~s_PrevExtra;
    u32 dir;
    s32 spell;
    u16 pressed;

    s_PrevExtra = extra;
    if (g_GameState != Game_Play || g_GameEngineStep != Engine_Normal ||
        CharacterLoaded() != CHAR_ALUCARD || (g_Player.status & PLAYER_STATUS_TRANSFORM)) {
        s_Steps = NULL;
        return;
    }
    if (!s_Steps && flicked) {
        for (dir = 0; dir < 4; dir++) {
            if ((flicked & (PADX_RS_UP << dir)) && (spell = Chosen(dir)) >= 0) {
                s_Steps = s_Spells[spell].steps;
                s_Count = s_Spells[spell].count;
                s_Step = s_Held = 0;
                s_FacingLeft = PLAYER.facingLeft;
                s_PrevPressed = 0;
                break;
            }
        }
    }
    if (!s_Steps) {
        return;
    }
    pressed = Buttons(s_Steps[s_Step].buttons);
    g_pads[0].pressed = pressed;
    g_pads[0].tapped = pressed & ~s_PrevPressed;
    s_PrevPressed = pressed;
    if (++s_Held >= s_Steps[s_Step].frames) {
        s_Held = 0;
        if (++s_Step >= s_Count) {
            s_Steps = NULL;
        }
    }
}
