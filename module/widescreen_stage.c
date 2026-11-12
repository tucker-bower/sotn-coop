// Widescreen (design/M19-widescreen.md): the stage's windows for its entities, as wide as the view.
//
// Every stage's code keeps its entities within a window of the game's 256-wide view: Update
// destroys an entity past x -64..320 (-128..384 for some) and freezes others past -64..320, and the
// spawner (UpdateRoomPosition, InitRoomEntities) brings a room's objects in at scroll - 64 and
// scroll + 320 (src/st/st_update.h, src/st/create_entity.h). A wider view shows past those edges,
// where enemies would freeze, vanish or pop in. While the view is wide, each window's x bounds
// are moved out by the view's extra width: the immediates in those three functions, found by
// their values (each upper bound with the nearest matching lower bound, so the y bounds, which use
// the same lower values, stay), and put back when the view isn't wide.
//
// Most stages' Update compiles its windows unsigned instead (#260): `(u16)(x + 64) < 385` is
// `addiu 64; sltiu 385` (-64..320), and `addiu 128; sltiu 513` (-128..384). Only the spawner's
// windows were widened there, so a door or an enemy spawned in the extra width was destroyed the
// next frame and never came back (the spawner had passed it): no red door to walk through at
// 21:9. Their x windows (the y ones end at 353 and 481) get the offset and the width widened.
#define COOP_MODULE
#include <game.h>
#include "link.h"

void FlushCache(void); // main.exe

#define STAGE_HEADER ((Overlay*)0x80180000) // every stage's overlay starts with its table
#define SCAN_MAX 600                        // instructions per function, at most
#define NEAR 8                              // a lower bound's distance from its upper one
#define JR_RA 0x03E00008
#define OP(ins) ((ins) >> 26)
#define IMM(ins) ((s16)((ins) & 0xFFFF))
#define OP_ADDIU 0x09
#define OP_SLTI 0x0A
#define OP_SLTIU 0x0B
#define MAX_PATCHES 64

typedef struct {
    u32* at;
    u32 was, is;
} Patch;

static Patch s_Patches[MAX_PATCHES];
static s32 s_Count;
static void* s_PatchedUpdate; // which overlay's code is patched (its Update), and for what width
static s32 s_PatchedExtra;

static bool Imm(u32 ins) { return OP(ins) == OP_ADDIU || OP(ins) == OP_SLTI; }

static void Set(u32* at, s32 value) {
    if (s_Count >= MAX_PATCHES) {
        return;
    }
    s_Patches[s_Count].at = at;
    s_Patches[s_Count].was = *at;
    *at = (*at & 0xFFFF0000) | (value & 0xFFFF);
    s_Patches[s_Count].is = *at;
    s_Count++;
}

// The window's upper x bound and its lower partner: 320 (spawner) or 321 (Update's `x > 320`)
// with -64, and 385 with -128.
static s32 Lower(s32 upper) { return upper == 385 ? -128 : upper == 320 || upper == 321 ? -64 : 0; }

// An unsigned x window's size + 1 (sltiu), and its offset (the addiu just before it).
static s32 Offset(u32 ins) {
    return OP(ins) != OP_SLTIU ? 0 : IMM(ins) == 385 ? 64 : IMM(ins) == 513 ? 128 : 0;
}

static void Widen(u32* fn, s32 extra) {
    s32 i, j, lower, best, offset;

    for (i = 0; i < SCAN_MAX && fn[i] != JR_RA; i++) {
        if ((offset = Offset(fn[i]))) {
            for (j = i - 1; j >= 0 && j >= i - NEAR; j--) {
                if (OP(fn[j]) == OP_ADDIU && IMM(fn[j]) == offset) {
                    Set(&fn[j], offset + extra);
                    Set(&fn[i], IMM(fn[i]) + 2 * extra);
                    break;
                }
            }
            continue;
        }
        if (!Imm(fn[i]) || !(lower = Lower(IMM(fn[i])))) {
            continue;
        }
        best = -1;
        for (j = i - NEAR; j <= i + NEAR; j++) {
            if (j >= 0 && j != i && Imm(fn[j]) && IMM(fn[j]) == lower &&
                (best < 0 || (j > i ? j - i : i - j) < (best > i ? best - i : i - best))) {
                best = j;
            }
        }
        Set(&fn[i], IMM(fn[i]) + extra);
        if (best >= 0) {
            Set(&fn[best], lower - extra);
        }
    }
}

static void Restore(void) {
    while (s_Count) {
        s_Count--;
        *s_Patches[s_Count].at = s_Patches[s_Count].was;
    }
    s_PatchedUpdate = NULL;
    s_PatchedExtra = 0;
}

// Each frame: the current stage's windows for the view's extra width (0: the game's own).
void WidescreenStage(s32 extra) {
    Overlay* o = STAGE_HEADER;

    bool ours = s_Count && *s_Patches[0].at == s_Patches[0].is; // (a reload of the stage wipes them)

    if (!ours) {
        s_Count = 0;
        s_PatchedUpdate = NULL;
        s_PatchedExtra = 0;
        if (!extra) {
            return; // off, and nothing of ours in the code: the game's own windows
        }
    }
    if (s_PatchedUpdate == (void*)o->Update && s_PatchedExtra == extra) {
        return;
    }
    if (ours && s_PatchedUpdate == (void*)o->Update) {
        Restore(); // the same stage at another width
    } else {
        s_Count = 0; // a new stage's code was loaded over the old: nothing of ours is left in it
        s_PatchedUpdate = NULL;
    }
    if (extra > 0 && (u32)o->Update >= 0x80180000 && (u32)o->Update < 0x80280000) {
        Widen((u32*)o->Update, extra);
        Widen((u32*)o->UpdateRoomPosition, extra);
        Widen((u32*)o->InitRoomEntities, extra);
        s_PatchedUpdate = (void*)o->Update;
        s_PatchedExtra = extra;
    }
    FlushCache();
}

bool WidescreenStagePatched(void) { return s_Count != 0; }
