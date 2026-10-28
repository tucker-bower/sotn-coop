// The partner's hand-weapon swings on this screen (playtest 2026-10-25 note 2, phase 2;
// design/M12-coverage.md). A hand weapon's sprite table is in its overlay (0x8017A000 or
// 0x8017D000) and its tile sheet in VRAM (0x240,0x100 or 0x240,0x180): only the swinger's game
// has them. So when a weapon loads, each game copies its overlay, sheet and 24 palettes to
// WEAPON_SELF_ADDR, and the host sends that copy to the partner's WEAPON_PARTNER_ADDR. The
// swing's sprites come with the others (sprites.c); this game draws them as RenderEntities draws a
// weapon's frame, with each frame's parts and palettes put into the VRAM window (D106).
// Not yet: the weapons whose sprites are in their second bank (5 of them), and rotated or scaled
// frames (drawn upright).
#define COOP_MODULE
#include <game.h>
#include "link.h"
#include "character.h"
#include "offhand.h"
#include "weapons.h"
#include "partner.h"

#define WEAPON_PRG(hand) ((hand) ? 0x8017D000 : 0x8017A000)
#define ANIMSET_OFS 0x40 // every weapon overlay's first sprite table (offhand.c's WEAPON_ANIMSET)
#define PAL_WEAPONS 0x110 // a hand's 24 palettes from here (src/weapon/shared.h)
#define N_WEAPON_PAL 24
#define SHEET_X 0x240 // where DRA loads a hand's sheet (src/dra/47BB8.c), in VRAM words
#define SHEET_Y(hand) ((hand) ? 0x180 : 0x100)
#define SHEET_W 0x40
#define SHEET_H 0x80
#define SHEET_TPAGE 0x19 // its texture page (0x240, 0x100): a weapon's tpage + unk5A, >> 2
#define UNK5A(hand) (0x64 + (hand) * 2) // what a weapon entity sets for each hand
#define COPY_DELAY 30   // frames after the load: the menu's InitWeapon loads the palettes after it
#define CLUT_CHECK 60   // frames between checks of Alucard's weapon palettes (a few change them)

static s16 s_CopyIn[2]; // frames until this hand's copy is made (0: none pending)
static bool s_ClutKept[2]; // Richter, Maria: the palettes were kept as they loaded (FixPalettes)
static u16 s_ClutAge;

static CoopWeapon* Self(s32 hand) { return (CoopWeapon*)(WEAPON_SELF_ADDR + hand * WEAPON_HAND_SIZE); }

static const CoopWeapon* Partner(s32 hand) {
    return (const CoopWeapon*)(WEAPON_PARTNER_ADDR + hand * WEAPON_HAND_SIZE);
}

static u16* WeaponClut(s32 hand) { return (u16*)g_Clut + (PAL_WEAPONS + hand * N_WEAPON_PAL) * COLORS_PER_PAL; }

// --- this game's weapons, for the partner -----------------------------------------------------

static bool SameClut(const u16* a, const u16* b) {
    const u32* x = (const u32*)a;
    const u32* y = (const u32*)b;
    s32 k;

    for (k = 0; k < WEAPON_CLUT_SIZE / 4; k++) {
        if (x[k] != y[k]) {
            return false;
        }
    }
    return true;
}

// The CD just loaded a hand's weapon (character.c): its sheet is in VRAM now (before Maria's
// guardians go back over it); the rest is copied once the menu has set it up.
void WeaponLoaded(s32 hand) {
    RECT r;

    r.x = SHEET_X;
    r.y = SHEET_Y(hand);
    r.w = SHEET_W;
    r.h = SHEET_H;
    DrawSync(0);
    StoreImage(&r, (u_long*)Self(hand)->sheet);
    DrawSync(0);
    s_CopyIn[hand] = COPY_DELAY;
}

// Richter's and Maria's games: a hand's weapon palettes, just loaded over the player's own
// (offhand.c's FixPalettes puts those back right after).
void WeaponKeepClut(s32 hand, const u16* clut) {
    CoopWeapon* w = Self(hand);

    __builtin_memcpy(w->clut, clut, WEAPON_CLUT_SIZE);
    s_ClutKept[hand] = true;
    if (!s_CopyIn[hand] && w->magic == WEAPON_MAGIC) {
        w->seq++;
    }
}

// Once per frame.
void WeaponsUpdate(void) {
    CoopWeapon* w;
    s32 hand;
    bool check = ++s_ClutAge >= CLUT_CHECK;

    if (check) {
        s_ClutAge = 0;
    }
    for (hand = 0; hand < 2; hand++) {
        w = Self(hand);
        if (s_CopyIn[hand] && !--s_CopyIn[hand]) {
            __builtin_memcpy(w->ovl, (const void*)WEAPON_PRG(hand), WEAPON_OVL_SIZE);
            if (!s_ClutKept[hand] || CharacterLoaded() == CHAR_ALUCARD) {
                __builtin_memcpy(w->clut, WeaponClut(hand), WEAPON_CLUT_SIZE);
            }
            s_ClutKept[hand] = false;
            w->item = g_Status.equipment[hand];
            w->magic = WEAPON_MAGIC;
            w->seq++;
        } else if (check && !s_CopyIn[hand] && w->magic == WEAPON_MAGIC && CharacterLoaded() == CHAR_ALUCARD &&
                   !SameClut(w->clut, WeaponClut(hand))) {
            __builtin_memcpy(w->clut, WeaponClut(hand), WEAPON_CLUT_SIZE);
            w->seq++;
        }
    }
}

// --- the partner's, drawn here ----------------------------------------------------------------
// The window (D106: VRAM words 0x1E0-0x1FF, rows 0x100-0x1DF) is the right half of texture page
// 0x1C0,0x100: tiles from its top, a hand's 24 palettes (two to a row) in its last 24 rows.
#define WIN_X 0x1E0
#define WIN_Y 0x100
#define WIN_W 0x20
#define WIN_H 0xE0
#define WIN_TILES_H (WIN_H - 2 * N_WEAPON_PAL / 2)
#define WIN_PAL_ROW(hand, pal) (WIN_TILES_H + (hand) * N_WEAPON_PAL / 2 + (pal) / 2)
#define WIN_TPAGE 0x17 // GetTPage(0, 0, 0x1C0, 0x100): the window is its u 0x80-0xFF
#define CLUT_ID(x, y) (((y) << 6) | ((x) >> 4))
#define DRAW_SCALE_ROTATE (ENTITY_SCALEX | ENTITY_SCALEY | ENTITY_ROTATE)

static u16 s_Win[WIN_H][WIN_W]; // the window's picture this frame
static s32 s_CurX, s_CurY, s_ShelfH; // where the next tiles go (words, rows), and this row's height
static u8 s_PalsIn; // hands whose palettes are in the picture (bits)

// The sheet's pixels [sx, sx + w) x [sy, sy + h) into the picture; *u, *v: where (sx, sy) went,
// in the window's pixels. False if they don't fit.
static bool Place(const u16* sheet, s32 sx, s32 sy, s32 w, s32 h, s32* u, s32* v) {
    s32 w0 = sx >> 2, nw = ((sx + w + 3) >> 2) - w0, row, k;

    if (nw > WIN_W || h > WIN_TILES_H) {
        return false;
    }
    if (s_CurX + nw > WIN_W) {
        s_CurX = 0;
        s_CurY += s_ShelfH;
        s_ShelfH = 0;
    }
    if (s_CurY + h > WIN_TILES_H) {
        return false;
    }
    for (row = 0; row < h; row++) {
        for (k = 0; k < nw; k++) {
            s_Win[s_CurY + row][s_CurX + k] = sheet[(sy + row) * SHEET_W + w0 + k];
        }
    }
    *u = s_CurX * 4 + (sx & 3);
    *v = s_CurY;
    s_CurX += nw;
    if (h > s_ShelfH) {
        s_ShelfH = h;
    }
    return true;
}

// Palette pal's CLUT: the weapon's own are in the window; any other is this game's too.
static u16 Clut(s32 hand, s32 pal) {
    s32 k, row, rel = pal - (PAL_WEAPONS + hand * N_WEAPON_PAL);

    if (rel < 0 || rel >= N_WEAPON_PAL) {
        return g_ClutIds[pal];
    }
    if (!(s_PalsIn & (1 << hand))) {
        s_PalsIn |= 1 << hand;
        for (k = 0; k < N_WEAPON_PAL * COLORS_PER_PAL; k++) {
            row = WIN_PAL_ROW(hand, k / COLORS_PER_PAL);
            s_Win[row][((k / COLORS_PER_PAL) & 1) * COLORS_PER_PAL + k % COLORS_PER_PAL] = Partner(hand)->clut[k];
        }
    }
    return CLUT_ID(WIN_X + (rel & 1) * COLORS_PER_PAL, WIN_Y + WIN_PAL_ROW(hand, rel));
}

// The frame's parts (SpriteParts, in the partner's overlay copy), or NULL.
static const s16* Frame(const CoopWeapon* w, s32 hand, s32 pose) {
    const u32* table = (const u32*)(w->ovl + ANIMSET_OFS);
    u32 parts;

    if (pose <= 0 || ANIMSET_OFS + (pose + 1) * 4 > WEAPON_OVL_SIZE) {
        return NULL;
    }
    parts = table[pose] - WEAPON_PRG(hand);
    if (table[pose] < WEAPON_PRG(hand) || parts + 2 > WEAPON_OVL_SIZE) {
        return NULL;
    }
    return (const s16*)(w->ovl + parts);
}

// One sprite: each part as RenderEntities draws it (src/dra/4B758.c, the sprite parts branch).
static void Draw(const CoopSprite* s, s32 hand) {
    const CoopWeapon* w = Partner(hand);
    const s16* f = Frame(w, hand, s->animCurFrame & 0x7FFF);
    const s16* part;
    POLY_GT4* poly;
    s32 n, i, flags, tp, x, y, px, py, pw, ph, flipX, flip;
    s32 uR, vT, uL, vB, sx, sy, ue, ve, u, v;
    u8 u0, u1, v0, v1;

    if (!f || f[0] <= 0 || f[0] > 16 || 2 + f[0] * 22 > WEAPON_OVL_SIZE - ((const u8*)f - w->ovl)) {
        return;
    }
    n = f[0];
    x = s->x - g_Tilemap.scrollX.i.hi + g_cameraOffsetX;
    y = s->y - g_Tilemap.scrollY.i.hi + g_cameraOffsetY;
    if (x < -512 || x > 512 || y < -512 || y > 512) {
        return;
    }
    flipX = s->facingLeft << 1;
    for (i = 0, part = f + 1; i < n; i++, part += 11) {
        if (g_GpuUsage.gt4 >= MAX_POLY_GT4_COUNT) {
            return;
        }
        flags = part[0];
        tp = part[6] + s->unk5A;
        if ((tp >> 2) != SHEET_TPAGE) {
            continue;
        }
        px = part[1];
        py = part[2];
        pw = part[3];
        ph = part[4];
        if (flags & 4) {
            pw--;
            if (flags & 2) {
                px++;
            }
        }
        if (flags & 8) {
            ph--;
            if (flags & 1) {
                py++;
            }
        }
        if (flags & 0x10) {
            pw--;
            if (!(flags & 2)) {
                px++;
            }
        }
        if (flags & 0x20) {
            ph--;
            if (!(flags & 1)) {
                py++;
            }
        }
        // The texture, in the hand's sheet: u from 0x240, v from its row (hand 1's is 0x80 down)
        uR = (u8)part[7] + (tp & 1 ? 0x80 : 0);
        vT = (u8)part[8] + (tp & 2 ? 0x80 : 0) - hand * SHEET_H;
        uL = (u8)part[9] + (tp & 1 ? 0x80 : 0);
        vB = (u8)part[10] + (tp & 2 ? 0x80 : 0) - hand * SHEET_H;
        if (flags & 4) {
            uL--;
        }
        if (flags & 8) {
            vB--;
        }
        if (flags & 0x10) {
            uR++;
        }
        if (flags & 0x20) {
            vT++;
        }
        sx = (uR < uL ? uR : uL) - 1; // one pixel either side: the flipped UVs reach it
        sy = (vT < vB ? vT : vB) - 1;
        if (sx < 0) {
            sx = 0;
        }
        if (sy < 0) {
            sy = 0;
        }
        ue = (uR > uL ? uR : uL) + 1;
        ve = (vT > vB ? vT : vB) + 1;
        if (ue > SHEET_W * 4) {
            ue = SHEET_W * 4;
        }
        if (ve > SHEET_H) {
            ve = SHEET_H;
        }
        if (ue <= sx || ve <= sy || !Place(w->sheet, sx, sy, ue - sx, ve - sy, &u, &v)) {
            continue;
        }
        // From the sheet's pixels to the window's (u 0x80 on in its texture page)
        uR += 0x80 + u - sx;
        uL += 0x80 + u - sx;
        vT += v - sy;
        vB += v - sy;

        poly = &g_CurrentBuffer->polyGT4[g_GpuUsage.gt4];
        setPolyGT4(poly);
        px = s->facingLeft ? x - px : x + px;
        py += y;
        if (flipX) {
            setXY4(poly, px - pw + 1, py, px + 1, py, px - pw + 1, py + ph, px + 1, py + ph);
        } else {
            setXY4(poly, px, py, px + pw, py, px, py + ph, px + pw, py + ph);
        }
        flip = (flags & 2) ^ flipX;
        u0 = flip ? uL - 1 : uR;
        u1 = flip ? uR - 1 : uL;
        v0 = (flags & 1) ? vB - 1 : vT;
        v1 = (flags & 1) ? vT - 1 : vB;
        setUV4(poly, u0, v0, u1, v0, u0, v1, u1, v1);
        poly->tpage = WIN_TPAGE;
        poly->clut = Clut(hand, (s->palette & PAL_UNK_FLAG) ? s->palette & 0x7FFF : part[5] + s->palette);
        if (s->blendMode) {
            setSemiTrans(poly, true);
            poly->tpage += s->blendMode & BLEND_QUARTER;
        } else {
            setSemiTrans(poly, false);
        }
        setShadeTex(poly, true);
        addPrim(&g_CurrentBuffer->ot[s->zPriority + (flags & 0x100 ? 4 : 0)], poly);
        g_GpuUsage.gt4++;
    }
}

static bool PartnerHere(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    return g_CoopLink.partnerAge <= 30 && (p->flags & PRESENCE_IN_PLAY) && SAME_WORLD(p) &&
           p->stage == g_StageId && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top;
}

u32 g_CoopWeaponsDrawn; // sprites drawn last frame (tests read it: coop.map)

// After RenderEntities: the partner's weapon sprites.
void WeaponsDraw(void) {
    const CoopSprite* s;
    RECT r;
    s32 k, hand, before = g_GpuUsage.gt4;
    CoopSprite moved;
    s16 dx = 0, dy = 0;
    bool sim;

    g_CoopWeaponsDrawn = 0;
    if (g_GameState != Game_Play || !PartnerHere()) {
        return;
    }
    s_CurX = s_CurY = s_ShelfH = 0;
    s_PalsIn = 0;
    sim = PartnerSimulated();
    if (sim) {
        PartnerBodyOffset(&dx, &dy);
    }
    for (k = 0; k < (s32)g_CoopLink.partnerSpriteCount && k < COOP_SPRITES; k++) {
        s = &g_CoopLink.partnerSprites[k];
        hand = s->weapon & 1;
        if (!(s->weapon & WEAPON_SPRITE) || Partner(hand)->magic != WEAPON_MAGIC ||
            (s->animSet & 0x7FFF) != 0x10 + hand * 2) { // the second bank: not yet
            continue;
        }
        if (sim) { // M13: only a weapon the body can't run, where the body is (partner.c)
            if (!PartnerWeaponDiffers(hand)) {
                continue;
            }
            moved = *s;
            moved.x += dx;
            moved.y += dy;
            s = &moved;
        }
        Draw(s, hand);
        g_CoopWeaponsDrawn++;
    }
    if (g_GpuUsage.gt4 != before) {
        r.x = WIN_X;
        r.y = WIN_Y;
        r.w = WIN_W;
        r.h = WIN_H;
        LoadImage(&r, (u_long*)s_Win);
    }
}

// This game's sprite of entity e, if it's a hand weapon's (sprites.c): as the partner draws it.
bool WeaponSprite(Entity* e, CoopSprite* s) {
    s32 set, hand;
    u16 palette;

    if (!(e->animSet & ANIMSET_OVL_FLAG)) {
        return false;
    }
    set = e->animSet & 0x7FFF;
    if (CharacterLoaded() == CHAR_ALUCARD) {
        if (set < 0x10 || set >= 0x14) {
            return false;
        }
        hand = (set - 0x10) >> 1;
        palette = e->palette;
    } else if (!OffhandOriginal(e, &set, &palette, &hand)) {
        return false;
    }
    s->animSet = ANIMSET_OVL(set);
    s->palette = palette;
    s->unk5A = UNK5A(hand);
    s->weapon = WEAPON_SPRITE | hand;
    return true;
}
