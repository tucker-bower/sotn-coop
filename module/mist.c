// Mist Step (design/M8b §3.1): Richter and Maria, with Alucard's Form of Mist, pass the grates
// only mist goes through (EFFECT_MIST_ONLY). They keep walking into one for half a second,
// dissolve, drift through (walking, unseen) and reform on the far side. Power of Mist lifts the length limit.
// While they drift, their collision ignores mist-only tiles, the way Alucard's does in mist
// (src/dra/692E8.c): the module swaps g_api.CheckCollision for the frame, so it needs no change
// to their overlays, works the same for both, and is deterministic.
#define COOP_MODULE
#include <game.h>
#include <sfx.h>
#include "character.h"
#include "link.h"
#include "mist.h"

void CheckCollision(s32 x, s32 y, Collider* res, s32 unk); // DRA
void PlaySfx(s32 sfxId);                                   // DRA

#define PUSH_FRAMES 30   // walking into the grate this long starts the step
#define FADE_FRAMES 8    // dissolving, then as long reforming
#define PROBE_AHEAD 10   // px ahead of the player's center
#define BODY 48          // px of clear space the player ends up in the middle of
#define SHORT_REACH 40   // px of grate: without Power of Mist, about 2 tiles (Alucard's in practice)
#define LONG_REACH 1024  // px: with it
#define PL_T_INVINCIBLE 14 // Richter's (src/ric/ric_shared.h) and Maria's player timers

enum { MIST_IDLE, MIST_FADE_OUT, MIST_DRIFT, MIST_FADE_IN };

static s32 s_State, s_Timer, s_Dir;
static s32 s_TargetX; // in the room (world) pixels
static void (*s_Collision)(s32 x, s32 y, Collider* res, s32 unk);

static u32 Effects(s32 x, s32 y) {
    Collider col;
    CheckCollision(x, y, &col, 0);
    return col.effects;
}

// The body's column at x (screen): what's there at the legs and at the chest.
static u32 Column(s32 x) {
    s32 y = PLAYER.posY.i.hi;
    return Effects(x, y + 8) | Effects(x, y - 16);
}

// Where (screen x) the player can stand beyond the grate ahead, or 0 if it's too long or solid.
static s32 FarSide(s32 dir) {
    s32 reach = (g_Status.relics[RELIC_POWER_OF_MIST] & RELIC_FLAG_ACTIVE) ? LONG_REACH : SHORT_REACH;
    s32 x0 = PLAYER.posX.i.hi + dir * PROBE_AHEAD, d, clear = 0;
    u32 e;

    for (d = 0; d <= reach + BODY; d += 2) {
        e = Column(x0 + dir * d);
        if (e & EFFECT_MIST_ONLY) {
            clear = 0;
        } else if (e & EFFECT_SOLID) {
            return 0; // a real wall behind the grate
        } else if ((clear += 2) >= BODY) {
            return x0 + dir * (d - BODY / 2); // the middle of the clear stretch
        }
    }
    return 0;
}

// The player's collision while drifting: mist-only tiles aren't there.
static void MistCollision(s32 x, s32 y, Collider* res, s32 unk) {
    CheckCollision(x, y, res, unk);
    if (res->effects & EFFECT_MIST_ONLY) {
        res->effects = EFFECT_NONE;
    }
}

void MistStepUpdate(void) {
    s32 dir, x;

    if (g_GameState != Game_Play || g_GameEngineStep != Engine_Normal || g_StageId == STAGE_ST0 ||
        CharacterLoaded() == CHAR_ALUCARD || g_Status.hp <= 0) {
        s_State = MIST_IDLE;
        s_Timer = 0;
        return;
    }
    switch (s_State) {
    case MIST_IDLE:
        dir = (g_pads[0].pressed & PAD_RIGHT) ? 1 : (g_pads[0].pressed & PAD_LEFT) ? -1 : 0;
        if (!dir || !(g_Status.relics[RELIC_FORM_OF_MIST] & RELIC_FLAG_ACTIVE) ||
            !(Column(PLAYER.posX.i.hi + dir * PROBE_AHEAD) & EFFECT_MIST_ONLY)) {
            s_Timer = 0;
            return;
        }
        if (dir != s_Dir) {
            s_Dir = dir;
            s_Timer = 0;
        }
        if (++s_Timer < PUSH_FRAMES) {
            return;
        }
        s_Timer = 0;
        x = FarSide(dir);
        if (!x) {
            return;
        }
        s_TargetX = x + g_Tilemap.scrollX.i.hi;
        PlaySfx(SFX_TRANSFORM);
        s_State = MIST_FADE_OUT;
        break;
    case MIST_FADE_OUT:
        if (++s_Timer >= FADE_FRAMES) {
            s_Timer = 0;
            s_State = MIST_DRIFT;
        }
        break;
    case MIST_DRIFT:
        x = PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi;
        if (s_Dir * (s_TargetX - x) <= 0 || ++s_Timer > LONG_REACH) {
            s_Timer = 0;
            s_State = MIST_FADE_IN;
            break;
        }
        // The player walks through: the grate isn't there for their collision this frame.
        s_Collision = g_api.CheckCollision; // until the frame's update is over (MistStepAfter)
        g_api.CheckCollision = MistCollision;
        g_pads[0].pressed = s_Dir > 0 ? PAD_RIGHT : PAD_LEFT;
        g_pads[0].tapped = g_pads[0].repeat = 0;
        g_Player.timers[PL_T_INVINCIBLE] = 2;
        return;
    case MIST_FADE_IN:
        if (++s_Timer >= FADE_FRAMES) {
            s_State = MIST_IDLE;
            s_Timer = 0;
            return;
        }
        break;
    }
    // While stepping: no input, standing still, unhurt.
    g_pads[0].pressed = g_pads[0].tapped = g_pads[0].repeat = 0;
    PLAYER.velocityX = PLAYER.velocityY = 0;
    g_Player.timers[PL_T_INVINCIBLE] = 2;
}

// After the frame's update: the real collision is back.
void MistStepAfter(void) {
    if (s_Collision) {
        g_api.CheckCollision = s_Collision;
        s_Collision = NULL;
    }
}

// Before RenderEntities: the player flickers out, isn't there while drifting, and flickers in.
bool MistStepHidden(void) {
    switch (s_State) {
    case MIST_FADE_OUT:
        return s_Timer >= FADE_FRAMES / 2 || (s_Timer & 1);
    case MIST_DRIFT:
        return true;
    case MIST_FADE_IN:
        return s_Timer < FADE_FRAMES / 2 && !(s_Timer & 1);
    }
    return false;
}
