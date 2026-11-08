// SPDX-License-Identifier: AGPL-3.0-or-later
// Saturn Maria's own HUD (docs/design/character-mods.md, D182): the Saturn's compact status
// display, from SOTN Ultimate's src/maria_saturn/5F60C_mod_maria_hud.h (df11991, by renanbianchi),
// which its DRA draws in place of Richter's. Our DRA has no room for that, so it's here: the
// module calls CoopSatMarHud (at a fixed address: sat_maria.ld) every frame once DRA's Richter
// HUD is drawn, and it hides that HUD and draws hers on sprites of her own. Her art
// (mar_hud_vram) is made from the player's Saturn disc (launcher/saturn_maria.py hud_vram) and
// uploaded into F_GAME2's empty VRAM, where Ultimate's disc has it.
//
// What differs from Ultimate's: her own sprites (forward-allocated, again whenever the HUD's are
// new or hers were freed) and her own shown HP; DRA's Richter HUD still advances the pause
// animation (g_PlayerHud.unk24), so this only reads it; and her HP bar and digits use 0x109, a
// copy of the Saturn's palette 0 (Ultimate's use 0x103, which on our disc is mostly black).
#include <game.h>
#include "mar_hud.h" // u16 mar_hud_vram[]: characters/maria-saturn/gen_headers.py

typedef struct {
    s32 x, y, w, h, u, v, tpage, clut;
} SubwpnIconParams; // src/dra/dra.h RicSubwpnIconParams

typedef struct {
    u32 displayHP;
    s32 primIndex1;
    s32 primIndex2;
    s32 unk0C;
    u32 unk10;
    s32 unk14;
    u32 unk18;
    u32 unk1C;
    u32 unk20;
    u32 unk24;
    s32 unk28;
} PlayerHudPart; // src/dra/dra.h PlayerHud
#define HUD (*(PlayerHudPart*)0x8013796C)                          // g_PlayerHud
#define HUD_STATE (*(u32*)0x8003C744)                             // D_8003C744: 5, the HUD hidden
#define RIC_SUBWPN_ICONS ((SubwpnIconParams*)0x800A3014)          // g_ricSubwpnIcons
#define RIC_HUD_SPRITES 9

#define MAR_HUD_TPAGE 0x18
#define MAR_HUD_V 136
#define MAR_HUD_CLUT 0x106
#define MAR_HUD_CLUT_BARS (MAR_HUD_CLUT + 3) // 0x109: the Saturn's palette 0, untouched by the glow
#define MAR_HUD_SPRITES 8
static RECT g_MarHudArtRect = {544, 392, 32, 96};

// palettes 0x106 (the Saturn's palette 0), 0x107 (MP bar, colours 1-3: set every frame), 0x108
// (the Saturn's palette 1)
static u16 g_MarHudPal[] = {
    0x0000, 0xFE9F, 0xFCDA, 0xCCF8, 0x8013, 0x801F, 0xA99F, 0xDEDF,
    0x8000, 0xBC00, 0x88CA, 0x952D, 0xAA16, 0xCF7F, 0xEFFF, 0xFFFF,
    0x0000, 0xFD8C, 0xFD8C, 0xFD8C, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
    0x0000, 0x8C97, 0x8415, 0xFFFF, 0x98C6, 0x8CC2, 0x8000, 0xEFFF,
    0xCE73, 0xB38C, 0x8D43, 0x95C5, 0x9A28, 0x96A6, 0x9122, 0xB18C,
    0x0000, 0xFE9F, 0xFCDA, 0xCCF8, 0x8013, 0x801F, 0xA99F, 0xDEDF, // 0x109
    0x8000, 0xBC00, 0x88CA, 0x952D, 0xAA16, 0xCF7F, 0xEFFF, 0xFFFF};
// the Saturn's palettes 3/4 (letters red / green) and 5/6: colours 9 (background) and 15 (letters)
static u16 g_MarHudGlow[][2] = {{0xBC00, 0x801F}, {0xBC00, 0x83E0}, {0x83E0, 0xFC00}, {0xFFFF, 0x801F}};
// the Saturn's palette 10, the full MP bar's colour ramp (red to white)
static u16 g_MarHudMpRamp[] = {
    0xB0A5, 0x843F, 0x8C7F, 0x94BF, 0x9CFF, 0xA53F, 0xAD7F, 0xB5BF,
    0xBDFF, 0xC63F, 0xCE7F, 0xD6BF, 0xDEFF, 0xE73F, 0xF7BF, 0xFD8C};
static RECT g_MarHudClutRect = {(MAR_HUD_CLUT - 0x100) * COLORS_PER_PAL, 0xF0, COLORS_PER_PAL * 4, 1};
// the pause animation's sprite for each step of g_PlayerHud.unk24: {y, h, v}
static u8 g_MarHudPauseStep[] = {1, 6, 12, 17, 51, 57, 61, 66};
static u8 g_MarHudPauseFrame[] = {1, 2, 3, 4, 3, 2, 1, 0};
static u8 g_MarHudPauseSpr[][3] = {
    {21, 24, MAR_HUD_V}, {25, 16, 0}, {29, 8, 16}, {25, 16, 24}, {21, 24, 64}};

static s16 g_MarHudPrim = -1; // her first sprite
static s32 g_MarHudOf = -1;   // the Richter HUD's first sprite it went with
static s32 g_MarHudHp;        // the HP shown

static void MarHudPalettes(void) {
    u16* clut = &g_Clut[1][(MAR_HUD_CLUT - 0x100) * COLORS_PER_PAL];
    s32 i, t;

    for (i = 0; i < LEN(g_MarHudPal); i++) {
        clut[i] = g_MarHudPal[i];
    }
    // the glow: palette 3/4 above 100 frames of charge (every 8 frames), every 4 above 200,
    // palette 5/6 above 300
    t = (s32)g_Player.unk24;
    if (t > 100) {
        i = (g_GameTimer >> (t > 200 ? 2 : 3)) & 1;
        if (t > 300) {
            i += 2;
        }
        clut[9] = g_MarHudGlow[i][0];
        clut[15] = g_MarHudGlow[i][1];
    }
    // the MP bar: blue; at full MP a 1-14 triangle wave of the timer (red <-> white)
    t = 15;
    if (g_Status.mp == g_Status.mpMax) {
        t = g_Timer & 0x1F;
        if (t > 15) {
            t = 31 - t;
        }
        t++;
        if (t > 14) {
            t = 14;
        }
    }
    clut[17] = clut[18] = clut[19] = g_MarHudMpRamp[t];
    LoadImage(&g_MarHudClutRect, (u_long*)clut);
}

static Primitive* MarHudSprite(Primitive* prim, s32 x, s32 y, s32 w, s32 h, s32 u, s32 v) {
    prim->x0 = prim->x2 = x;
    prim->x1 = prim->x3 = x + w;
    prim->y0 = prim->y1 = y;
    prim->y2 = prim->y3 = y + h;
    prim->u0 = prim->u2 = u;
    prim->u1 = prim->u3 = u + w;
    prim->v0 = prim->v1 = v;
    prim->v2 = prim->v3 = v + h;
    prim->tpage = MAR_HUD_TPAGE;
    prim->clut = MAR_HUD_CLUT_BARS;
    prim->priority = 0x1F0;
    prim->drawMode = DRAW_ABSPOS;
    return prim->next;
}

static void MarHudHide(s32 index) {
    Primitive* prim;

    for (prim = index > 0 ? &g_PrimBuf[index] : NULL; prim; prim = prim->next) {
        prim->drawMode = DRAW_HIDE;
    }
}

static void MarHudUpdate(Primitive* prim) {
    Primitive* p;
    SubwpnIconParams* ptr;
    s32 i, d, n;

    MarHudPalettes();
    // the shown HP follows by 5 a frame
    n = g_Status.hp - g_MarHudHp;
    if (n > 5) {
        n = 5;
    }
    if (n < -5) {
        n = -5;
    }
    n += g_MarHudHp;
    g_MarHudHp = n;
    // the holder (under the rest)
    p = prim;
    prim = MarHudSprite(prim, 2, 24, 38, 96, 128, MAR_HUD_V);
    p->clut = MAR_HUD_CLUT + 2;
    p->priority = 0x1EF;
    // the bars rise from y 116 (the Saturn's bottom row) in its tubes
    n = g_Status.hpMax ? n * 90 / g_Status.hpMax : 0;
    p = prim;
    prim = MarHudSprite(prim, 6, 117 - n, 4, n, 240, MAR_HUD_V);
    if (n <= 0) {
        p->drawMode = DRAW_HIDE;
    }
    n = g_Status.mpMax ? g_Status.mp * 57 / g_Status.mpMax : 0;
    p = prim;
    prim = MarHudSprite(prim, 21, 117 - n, 3, n, 245, MAR_HUD_V);
    p->clut = MAR_HUD_CLUT + 1;
    p->priority = 0x1EE; // under the holder, whose glass highlight shows over it
    if (n <= 0) {
        p->drawMode = DRAW_HIDE;
    }
    // hearts, ones first: the tens only from 10, the hundreds from 100
    for (i = 0, n = g_Status.hearts; i < 3; i++, n /= 10) {
        p = prim;
        prim = MarHudSprite(prim, 27 - i * 7, 29, 7, 8, 168 + n % 10 * 7, MAR_HUD_V + 24);
        if (i && n == 0) {
            p->drawMode = DRAW_HIDE;
        }
    }
    // the subweapon icon, Richter's, in her vine ring (2 px lower)
    if (g_Status.subWeapon == 0) {
        prim->drawMode = DRAW_HIDE;
    } else {
        ptr = &RIC_SUBWPN_ICONS[g_Status.subWeapon - 1];
        MarHudSprite(prim, ptr->x + 2, ptr->y + 24, ptr->w, ptr->h, ptr->u, ptr->v);
        prim->tpage = ptr->tpage;
        prim->clut = ptr->clut;
        if (prim->clut == 0x17F) {
            prim->drawMode |= DRAW_TPAGE | DRAW_TRANSP;
        }
    }
    prim = prim->next;
    // the plate, or the pause animation's sprite
    n = HUD.unk24;
    d = 0;
    for (i = 0; i < LEN(g_MarHudPauseStep); i++) {
        if (n >= g_MarHudPauseStep[i]) {
            d = g_MarHudPauseFrame[i];
        }
    }
    MarHudSprite(prim, 36, g_MarHudPauseSpr[d][0], 64, g_MarHudPauseSpr[d][1], d ? 64 : 168, g_MarHudPauseSpr[d][2]);
    prim->clut = MAR_HUD_CLUT;
    prim->priority = 0x1EF;
    if (d) {
        prim->tpage = 0x1B;
    }
}

static void CoopSatMarHud(void) {
    Primitive* prim;
    s32 i;

    if (HUD.primIndex1 <= 0) {
        return;
    }
    // her sprites, again whenever the HUD's are new (a stage's start frees them all) or hers were
    // freed; and her art with them (a load can bring F_GAME2 back over it)
    if (g_MarHudPrim < 0 || g_MarHudOf != HUD.primIndex1 || g_PrimBuf[g_MarHudPrim].type != PRIM_GT4) {
        g_MarHudPrim = g_api.AllocPrimitives(PRIM_GT4, MAR_HUD_SPRITES);
        g_MarHudOf = HUD.primIndex1;
        g_MarHudHp = g_Status.hp;
        if (g_MarHudPrim < 0) {
            return;
        }
        LoadImage(&g_MarHudArtRect, (u_long*)mar_hud_vram);
    }
    MarHudHide(HUD.primIndex1); // Richter's, which DRA just drew
    MarHudHide(HUD.primIndex2);
    prim = &g_PrimBuf[g_MarHudPrim];
    if (HUD_STATE == 5) { // DRA's "no HUD"
        for (i = 0; i < MAR_HUD_SPRITES && prim; i++, prim = prim->next) {
            prim->drawMode = DRAW_HIDE;
        }
        return;
    }
    MarHudUpdate(prim);
}

void (*CoopSatMarHooks[1])(void) = {CoopSatMarHud};
