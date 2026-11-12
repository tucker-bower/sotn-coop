// Widescreen (design/M19-widescreen.md): a wider view of the castle, not a stretch. Unfinished.
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

u16 g_CoopWideWidth; // tests: the view's width in pixels, over the player's setting; 0: the setting's

#define GP1(cmd) (*(volatile u32*)0x1F801814 = (cmd))
#define GP1_COOP_WIDE 0x2F000000
#define GP1_COOP_LINES 0x2E000000 // the lines shown: first | count << 9
void FlushCache(void); // main.exe
void WideTilemap(s32 columns); // widescreen_tilemap.c
void WidescreenStage(s32 extra); // widescreen_stage.c
bool WidescreenStagePatched(void);
void SetStageDisplayBuffer(void); // DRA

// The game's camera is left as it is: it keeps its 256-wide view of the room ("the game's view"),
// and the wider window is centred on it, slid to stay inside the room (or centred on a room narrower
// than it, the tilemap drawing nothing past the room's edges). Everything the game draws moves by
// the slide through the drawing offset; the tilemap, which draws from the camera's scroll, is drawn
// from that many pixels further left instead, through its one call (main loop, src/dra/5087C.c),
// with as many columns as the view needs (widescreen_tilemap.c).
#define RENDER_TILEMAP_CALL ((u32*)0x800E3D40)
#define JAL(fn) (0x0C000000 | (((u32)(fn) & 0x0FFFFFFF) >> 2))
void RenderTilemap(void); // DRA
s32 g_CoopWideSlide;   // how far the wide window starts left of the game's view (tests read it)
s32 g_CoopWideWindows;  // tests: the width the stage's entity windows are for (WindowsWidth)
u8 g_CoopWideStageOff; // tests: the stage's own entity windows (harness/widescreen_edges.py --raw)
static s32 s_Columns;

static void WideRenderTilemap(void) {
    s32 i;

    g_Tilemap.scrollX.i.hi -= g_CoopWideSlide;
    for (i = 0; i < MAX_BG_LAYER_COUNT; i++) {
        g_BgLayers[i].scrollX.i.hi -= g_CoopWideSlide;
    }
    g_cameraOffsetX -= g_CoopWideSlide;
    WideTilemap(s_Columns);
    g_cameraOffsetX += g_CoopWideSlide;
    for (i = 0; i < MAX_BG_LAYER_COUNT; i++) {
        g_BgLayers[i].scrollX.i.hi += g_CoopWideSlide;
    }
    g_Tilemap.scrollX.i.hi += g_CoopWideSlide;
}

static void TilemapCall(bool wide) {
    u32 want = JAL(wide ? (void*)WideRenderTilemap : (void*)RenderTilemap);

    if (*RENDER_TILEMAP_CALL != want && (*RENDER_TILEMAP_CALL == JAL(RenderTilemap) ||
                                         *RENDER_TILEMAP_CALL == JAL(WideRenderTilemap))) {
        *RENDER_TILEMAP_CALL = want;
        FlushCache();
    }
}

// How far the wide window starts left of the game's view: half the extra width in mid-room, less
// against the room's left edge, more against its right one.
static s32 Slide(s32 w) {
    s32 view = g_Tilemap.scrollX.i.hi, left = g_Tilemap.x, right = g_Tilemap.width, start;

    if (right - left >= w) {
        start = view - (w - DISP_STAGE_W) / 2;
        start = start < left ? left : start > right - w ? right - w : start;
    } else {
        start = left - (w - (right - left)) / 2;
    }
    return view - start;
}

// The HUD (priority 0x1EE-0x1F0, src/dra/5F60C.c) and whatever is drawn over it (message boxes)
// belong to the screen, not the castle: an offset command at the head of that layer of the ordering
// table takes the slide back off for them.
#define HUD_LAYER 0x1EE
// Over the HUD, from 0x1F1: dialogue, message boxes, the screen fade (0x1F8-0x1FF). They belong to
// the screen too, but in its middle: drawn centred on the wide view.
#define CENTRED_LAYER 0x1F1
static DR_OFFSET s_LayerOffset[2][2];
static s32 s_Wide; // the view's width this frame, while wide

static void Offset(DR_OFFSET* p, u32* slot, s32 x, s32 y) {
    p->code[0] = 0xE5000000 | ((y & 0x7FF) << 11) | (x & 0x7FF);
    p->tag = (1u << 24) | (*slot & 0xFFFFFF);
    *slot = (*slot & 0xFF000000) | ((u32)p & 0xFFFFFF);
}

void WidescreenAfterPrims(void) {
    DRAWENV* d = &g_CurrentBuffer->draw;
    DR_OFFSET* p = s_LayerOffset[g_CurrentBuffer == &g_GpuBuffers[1]];

    if (!s_Wide) {
        return;
    }
    Offset(&p[0], (u32*)&g_CurrentBuffer->ot[HUD_LAYER], d->clip.x, d->ofs[1]);
    Offset(&p[1], (u32*)&g_CurrentBuffer->ot[CENTRED_LAYER], d->clip.x + (s_Wide - DISP_STAGE_W) / 2, d->ofs[1]);
}

// The screen fade (InitFade, src/dra/624DC.c): four tiles, two side by side, 128 wide each, at the
// fade's layer. While wide they're as wide as the view (drawn centred, as above).
#define FADE_PRIM (*(s32*)0x8013799C) // fade.fadePrim
#define FADE_HALF 128

// w: the view's width, or 0 to put them back (only if they're still as we left them: was).
static void FadeWidth(s32 w, s32 was) {
    Primitive* prim;
    s32 i, half = w ? w / 2 : FADE_HALF, left = w ? -(w - DISP_STAGE_W) / 2 : 0;

    if (FADE_PRIM <= 0 || FADE_PRIM >= MAX_PRIM_COUNT) {
        return;
    }
    for (i = 0, prim = &g_PrimBuf[FADE_PRIM]; prim && i < 4; i++, prim = prim->next) {
        if (prim->type != PRIM_TILE || prim->v0 != 0xF0 || (!w && prim->u0 != was / 2)) {
            return; // not the fade's, or the game has set them since (the menu's SetFadeWidth): leave them
        }
        prim->x0 = left + half * (i & 1);
        prim->u0 = half;
    }
}

#define STAGE_CLIP_Y 0x14 // func_800E34DC (src/dra/42398.c): the stage view is drawn in lines 20-226
#define STAGE_CLIP_H 0xCF

// The player's screen shape (OPT_WIDE_*, link/mailbox.py WIDE_SHAPES): 4:3, 16:9, 21:9.
// The stage is drawn in 207 of the framebuffer's lines (STAGE_CLIP_*), and only those are shown wide:
// the game's pixels are 1.25 times as wide as tall, so 207 lines make 16:9 at 294 and 21:9 (64:27,
// a 2560x1080 screen) at 392.
static const u16 s_ShapeWidths[4] = {0, 294, 392, 0};
#define PARTNER_LINKED_FRAMES 600 // heard from within 10 s (as progress.c's PartnerLinked)

u16 WidescreenShape(void) { return (g_CoopLink.options & OPT_WIDE_MASK) >> OPT_WIDE_SHIFT; }

// The width the stage's entity windows are for: this player's view, or the partner's if wider, so
// that in a shared room the authority keeps enemies alive across the guest's whole view.
static s32 WindowsWidth(s32 w) {
    s32 theirs = s_ShapeWidths[(g_CoopLink.partner.aggroSwitches >> 14) & 3];

    return g_CoopLink.partnerAge < PARTNER_LINKED_FRAMES && theirs > w ? theirs : w;
}

void WidescreenFrame(void) {
    s32 w = (g_CoopWideWidth ? g_CoopWideWidth : s_ShapeWidths[WidescreenShape()]) & ~1, i, windows;
    DRAWENV* d0 = &g_GpuBuffers[0].draw;
    DRAWENV* d1 = &g_GpuBuffers[1].draw;
    static s32 s_Applied; // the width the framebuffers were last made (a change starts from it)
    s32 stage = (d0->clip.w == DISP_STAGE_W || d0->clip.w == s_Applied) && d0->clip.h == STAGE_CLIP_H &&
                d1->clip.y == STAGE_CLIP_Y; // not the CGI's layout, whose second buffer is lower

    static bool s_Off; // off, and everything put back: nothing to do each frame
    static u8 s_Remind;

    if (w > 512) {
        w = 512; // two side by side in the bank's 1024 columns
    }
    windows = g_CoopWideWindows = WindowsWidth(w);
    if (s_Off && !windows) { // (the default: as little as possible, the game's frame is tight)
        if (!(++s_Remind & 63)) {
            GP1(GP1_COOP_WIDE); // in case a state load left the core wide
        }
        return;
    }
    s_Off = false;
    if (g_GameState == Game_Play) {
        WidescreenStage(windows && !g_CoopWideStageOff ? windows - DISP_STAGE_W : 0);
    }
    if (!w || !stage || g_GameState != Game_Play) { // (the Game Over, the title: as the game draws them)
        if (stage && d0->clip.w != DISP_STAGE_W) { // turned off in play: the game's own framebuffers
            SetStageDisplayBuffer();
        }
        GP1(GP1_COOP_WIDE);
        TilemapCall(false);
        if (s_Wide) {
            FadeWidth(0, s_Wide);
        }
        g_CoopWideSlide = s_Wide = 0;
        s_Off = !windows && !WidescreenStagePatched() && !(stage && d0->clip.w != DISP_STAGE_W);
        return;
    }
    s_Columns = (w + 15) / 16 + 2;
    g_CoopWideSlide = Slide(w);
    GP1(GP1_COOP_LINES | STAGE_CLIP_Y | (STAGE_CLIP_H << 9));
    TilemapCall(true);
    for (i = 0; i < 2; i++) {
        DRAWENV* d = &g_GpuBuffers[i].draw;
        DISPENV* p = &g_GpuBuffers[i].disp;
        d->clip.x = i * w;
        d->ofs[0] = i * w + g_CoopWideSlide;
        d->clip.w = w;
        p->disp.x = (1 - i) * w; // shown while the other is drawn
        p->disp.w = w;
    }
    s_Applied = s_Wide = w;
    FadeWidth(w, 0);
    GP1(GP1_COOP_WIDE | w);
}
