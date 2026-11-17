// The pause menu for Richter and Maria: their own name and portrait (issue 27). The menu is
// Alucard's, so while it's open his portrait's pixels and palette in VRAM hold theirs, from their
// cutscene art on the player's disc (link/portraits.py), and what was there comes back when it
// closes. The familiar list's pictures too (FamiliarPics).
#define COOP_MODULE
#include <game.h>
#include "coop_api.h"
#include "character.h"
#include "link.h"
#include "portrait.h"

extern const char* g_MenuStr[]; // DRA: [0] is the status page's name

#define ART_W 48 // cutscene portraits: 8 bits per pixel
#define ART_H 72
#define MENU_W 64 // the menu's picture
#define MENU_H 96
#define MENU_X 0x300 // where it is in VRAM: 8 bits per pixel, so 2 pixels to a word
#define MENU_Y 0x180
#define PAL_MENU 0x150
#define PAL_COLORS 128 // the rest of the row is the menu's own

typedef struct {
    u32 pixels, palette; // offsets from PORTRAIT_ADDR: see link/portraits.py
    const char* name;    // in the menu font's encoding: ASCII - 0x20, 0xFF ends it
} Portrait;

static const Portrait s_Portraits[] = {
    [CHAR_RICHTER - 1] = {0x4, 0xD84, "\x32\x29\x23\x28\x34\x25\x32\xFF"},
    [CHAR_MARIA - 1] = {0xE84, 0x1C04, "\x2D\x21\x32\x29\x21\xFF"},
    [CHAR_ULT_MARIA - 1] = {0xE84, 0x1C04, "\x2D\x21\x32\x29\x21\xFF"}, // Maria's
    [CHAR_SAT_MARIA - 1] = {0xE84, 0x1C04, "\x2D\x21\x32\x29\x21\xFF"},
    [CHAR_ULT_RICHTER - 1] = {0x4, 0xD84, "\x32\x29\x23\x28\x34\x25\x32\xFF"}, // Richter's
};

static void Rects(RECT* pixels, RECT* palette) {
    u16 clut = g_ClutIds[PAL_MENU];

    pixels->x = MENU_X;
    pixels->y = MENU_Y;
    pixels->w = MENU_W / 2;
    pixels->h = MENU_H;
    palette->x = (clut & 0x3F) << 4;
    palette->y = clut >> 6;
    palette->w = PAL_COLORS;
    palette->h = 1;
}

static void Scale(const u8* art) {
    u8* out = (u8*)PORTRAIT_MENU_ADDR;
    s32 x, y;

    for (y = 0; y < MENU_H; y++) {
        for (x = 0; x < MENU_W; x++) {
            *out++ = art[(y * 3 / 4) * ART_W + x * 3 / 4];
        }
    }
}

// The familiar list's pictures (#298) are in Alucard's F_GAME.BIN only: its strip 0x1A, which the
// game's load puts at VRAM (0x380, 0x181), 32x127 (src/dra/cd.c), and palettes 0x1D0-0x1D6 (in
// row 0xFD). Richter's and Maria's games load F_GAME2.BIN, which has nothing there, and their
// own colours in that row: the familiars showed as blanks. While the menu is open they hold
// Alucard's, from CoopBoot's copy of F_GAME.BIN, and what was there comes back when it closes.
#define PICS_STRIP 0x1A
#define PICS_STRIP_BYTES 0x2000
#define PAL_PICS 0x1D0
#define PAL_PICS_N 7

static void PicsRect(RECT* r) {
    r->x = 0x380;
    r->y = 0x181;
    r->w = 0x20;
    r->h = 0x7F;
}

static void PalRect(RECT* r, s32 k) {
    u16 clut = g_ClutIds[PAL_PICS + k];

    r->x = (clut & 0x3F) << 4;
    r->y = clut >> 6;
    r->w = 16;
    r->h = 1;
}

static void FamiliarPics(bool open) {
    RECT r;
    s32 k;

    PicsRect(&r);
    if (open) {
        StoreImage(&r, (u_long*)FAMILIAR_PICS_SAVED_ADDR);
        DrawSync(0);
        LoadImage(&r, (u_long*)(FGAME_GFX_ADDR + PICS_STRIP * PICS_STRIP_BYTES));
    } else {
        LoadImage(&r, (u_long*)FAMILIAR_PICS_SAVED_ADDR);
    }
    for (k = 0; k < PAL_PICS_N; k++) {
        PalRect(&r, k);
        if (open) {
            StoreImage(&r, (u_long*)(FAMILIAR_PICS_SAVED_CLUT_ADDR + k * 32));
            DrawSync(0);
            LoadImage(&r, (u_long*)(FGAME_PAL_ADDR + (r.y - 0xF0) * 0x200 + r.x * 2));
        } else {
            LoadImage(&r, (u_long*)(FAMILIAR_PICS_SAVED_CLUT_ADDR + k * 32));
        }
    }
}

void PortraitUpdate(void) {
    static const char* alucard;
    static bool open, have;
    RECT pixels, palette;
    const Portrait* p;
    bool menu = g_GameState == Game_Play && g_GameEngineStep == Engine_Menu;

    if (!open && (!menu || CharacterLoaded() == CHAR_ALUCARD)) {
        return;
    }
    Rects(&pixels, &palette);
    if (!menu) {
        FamiliarPics(false);
        if (have) {
            LoadImage(&pixels, (u_long*)PORTRAIT_SAVED_ADDR);
            LoadImage(&palette, (u_long*)PORTRAIT_SAVED_CLUT_ADDR);
        }
        g_MenuStr[0] = alucard;
        open = false;
        return;
    }
    p = &s_Portraits[CharacterLoaded() - 1];
    if (!open) {
        alucard = g_MenuStr[0];
        g_MenuStr[0] = p->name;
        have = *(u32*)PORTRAIT_ADDR == PORTRAIT_MAGIC;
        open = true;
        FamiliarPics(true);
        if (have) {
            StoreImage(&pixels, (u_long*)PORTRAIT_SAVED_ADDR);
            DrawSync(0);
            StoreImage(&palette, (u_long*)PORTRAIT_SAVED_CLUT_ADDR);
            DrawSync(0);
            Scale((const u8*)(PORTRAIT_ADDR + p->pixels));
        }
    }
    if (have) {
        LoadImage(&pixels, (u_long*)PORTRAIT_MENU_ADDR); // every frame: the menu's own loads come first
        LoadImage(&palette, (u_long*)(PORTRAIT_ADDR + p->palette));
    }
}
