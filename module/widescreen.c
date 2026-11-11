// Widescreen (design/M19-widescreen.md), spike: a wider view of the castle, not a stretch.
//
// The game draws its stage view into two 256x240 framebuffers side by side in VRAM's top band,
// next to the stage's texture pages. Our core (patches/swanstation.patch, GP1 0x2F) takes a display
// width; while it's set, drawing, fills and the display in that band go to VRAM's second bank,
// where two framebuffers of up to 512 can sit side by side without touching any texture. Here the
// stage's two framebuffers are made that wide, each frame, and the core told the width; anything
// else (the menus, the title) runs as the game set it, with the core's width at 0.
#define COOP_MODULE
#include <game.h>
#include "link.h"

u16 g_CoopWideWidth; // the view's width in pixels; 0: off (tests, and later the launcher)

#define GP1(cmd) (*(volatile u32*)0x1F801814 = (cmd))
#define GP1_COOP_WIDE 0x2F000000
// RenderTilemap (src/dra/4CE2C.c) draws N_HORIZ_TILES (17) columns of 16 px, for the foreground and
// the background layers: `slti v0, t1, 17`, here made one more than the view needs.
#define TILE_COLUMN_SITES 2
static u32* const s_TileColumns[TILE_COLUMN_SITES] = {(u32*)0x800ED258, (u32*)0x800ED670};
#define SLTI_V0_T1 0x29220000
void FlushCache(void); // main.exe

static void TileColumns(s32 n) {
    bool changed = false;
    s32 i;

    for (i = 0; i < TILE_COLUMN_SITES; i++) {
        u32* p = s_TileColumns[i];
        if ((*p & 0xFFFF0000) == SLTI_V0_T1 && (*p & 0xFFFF) != (u32)n) {
            *p = SLTI_V0_T1 | n;
            changed = true;
        }
    }
    if (changed) {
        FlushCache();
    }
}

#define STAGE_CLIP_Y 0x14 // func_800E34DC (src/dra/42398.c): the stage view is drawn in lines 20-226
#define STAGE_CLIP_H 0xCF

void WidescreenFrame(void) {
    s32 w = g_CoopWideWidth & ~0xF, i;
    DRAWENV* d0 = &g_GpuBuffers[0].draw;
    DRAWENV* d1 = &g_GpuBuffers[1].draw;
    s32 stage = (d0->clip.w == DISP_STAGE_W || d0->clip.w == w) && d0->clip.h == STAGE_CLIP_H &&
                d1->clip.y == STAGE_CLIP_Y; // not the CGI's layout, whose second buffer is lower

    if (w > 512) {
        w = 512; // two side by side in the bank's 1024 columns
    }
    if (!w || !stage) {
        GP1(GP1_COOP_WIDE);
        TileColumns(N_HORIZ_TILES);
        return;
    }
    TileColumns(w / 16 + 1);
    for (i = 0; i < 2; i++) {
        DRAWENV* d = &g_GpuBuffers[i].draw;
        DISPENV* p = &g_GpuBuffers[i].disp;
        d->clip.x = d->ofs[0] = i * w;
        d->clip.w = w;
        p->disp.x = (1 - i) * w; // shown while the other is drawn
        p->disp.w = w;
    }
    GP1(GP1_COOP_WIDE | w);
}
