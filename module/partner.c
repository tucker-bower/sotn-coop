// M13 (design/M13-partner-player.md): the partner as a real second player. Each frame, after the
// game has updated player 1, the partner's copy of "the player" is swapped into RAM, the game's
// own player update runs on it with the partner's buttons (CoopLink.partnerPad, played out with
// its presence), and it's swapped back out. It exists while the partner is in our room, and is
// pulled to their real spot when it drifts past SNAP_PX. Cosmetic: no hit detection runs for it.
// Off unless OPT_PARTNER_SIM is set (not finished: familiars, sounds, Maria, an Alucard partner
// in another character's game). Without a partner (the harness's spike test), it's a copy of
// player 1 on g_CoopSpikePad.
//
// A Richter partner (step 3) runs our Richter linked to run there (PARTNER_RIC_ADDR,
// richter/ric_partner.ld), with statics of its own: for its frame, its g_PlOvl table and sprite
// table go into 0x8013C000 (where DRA looks), its sprite banks into g_api.o.spriteBanks[16..19],
// and the character to Richter's. In another character's game, its graphics (F_GAME2.BIN) are in
// VRAM's second bank, and what it draws reads them there (BankPolys).
#define COOP_MODULE
#include <game.h>
#include "coop_api.h"
#include "link.h"
#include "partner.h"
#include "puppet.h"

void EntityAlucard(void);        // DRA
void UpdatePlayerEntities(void); // DRA
void RenderEntities(void);       // DRA
void RenderPrimitives(void);     // DRA
u32 CharacterLoaded(void);       // character.c
void FlushCache(void);           // main.exe (PsyQ)
extern s16 D_800AC958[];         // DRA: the x of each of F_GAME's 32 strips (src/dra/cd.c)

// Everything that is "the player" (the other project's list, checked against the decomp).
typedef struct {
    u32 addr;
    u32 len;
} Region;
static const Region s_Regions[] = {
    {0x800733D8, 64 * 0xBC},            // g_Entities[0..63]: the player, afterimages, weapons, effects
    {0x80072BD0, 0x3D0},                // g_Player
    {0x80137FB4, 0x80138454 - 0x80137FB4}, // DRA's player statics
    {0x80097D1C, 0x280},                // g_PlayerDraw[16]
    {0x800ACF74, 8},                    // D_800ACF74, g_AlucardChairSleepTimer
    {0x8013B5E8, 4},                    // knockback invincibility, HUD HP delay
    {STATUS_A, STATUS_A_SIZE},          // g_Status: hp .. statsTotal (the partner's: PutStatus)
    {STATUS_B, STATUS_B_SIZE},          // g_Status: subWeapon .. elements
    {0x8013796C, 0x30},                 // g_PlayerHud
    {0x80139828, 0x40},                 // g_StatBuffTimers
    {0x80138FC0, 0x40},                 // g_ButtonCombo
};
#define BODY_SIZE (64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4) + 0x280 + 8 + 4 + 0x48 + 0x34 + 0x30 + 0x40 + 0x40)

// A partner who runs its own player code (Richter): what DRA reads at 0x8013C000 (g_PlOvl: the
// update functions, then the body's sprite table, which ends at 0x8013C334 in our Richter's file)
// and the four sprite banks its init installs (RicInit). Swapped with player 1's for its frames.
#define HDR_ADDR 0x8013C000
#define HDR_SIZE 0x334
static u32 s_Hdr[HDR_SIZE / 4];
static u32 s_Banks[4];
static u32 s_Char;    // CHAR_* of the body
static bool s_Code;   // it runs its own player code (not DRA's Alucard)
static bool s_Banked; // its graphics are in VRAM's second bank (another character than ours)
static s32 s_SavedChar;
static u32 s_SavedRandom;
static void (*s_SavedSfx)(s32);
static s32 (*s_SavedSfxVolPan)(s32, s32, s32);
static u32 s_BankLoaded = 0xFF; // CHAR_* whose graphics are in the second bank
static bool s_Reloaded; // the stage reloaded since Make (its primitives are gone with it)
CdlFILE g_CoopRicPartnerFile; // CoopBoot: COOPRICP.BIN (coop_api.h)
extern u32 g_randomNext; // DRA's Random()
u32 g_CoopSpikeBody[BODY_SIZE / 4]; // the partner's copy, while player 1's is in RAM (its entity 0 first)
static bool s_Made;
static u16 s_PrevPad;
static s16 s_ScrollX, s_ScrollY; // the camera when the copy was last swapped out
#define SNAP_PX 48

u32 g_CoopSpikePad;   // harness: the partner's buttons (PAD_*)
u32 g_CoopSpikeLines; // the last partner frame's cost, in scanlines (263 a frame)
u32 g_CoopSpikeMax;   // the most it has cost

// Graphics a partner's own code queues for DRA's loader (Maria's guardians, HUD): their entries
// (its own data) get the bank bit in their y, so the loader puts them in the second bank.
static u8 s_GfxBusy[LEN(g_GfxLoad)];

static void GfxBefore(void) {
    s32 i;

    for (i = 0; i < LEN(g_GfxLoad); i++) {
        s_GfxBusy[i] = g_GfxLoad[i].kind != GFX_BANK_NONE;
    }
}

static void GfxAfter(void) {
    GfxEntry* e;
    s32 i;

    for (i = 0; i < LEN(g_GfxLoad); i++) {
        if (!s_GfxBusy[i] && g_GfxLoad[i].kind != GFX_BANK_NONE) {
            for (e = g_GfxLoad[i].next; e->xy != GFX_TERMINATE(); e++) {
                e->xy = (u_long*)((u32)e->xy | (VRAM_BANK << 16));
            }
        }
    }
}

// Sounds of a partner's own code: its character's sound bank isn't in this game (step 4).
static void NoSfx(s32 id) {}
static s32 NoSfxVolPan(s32 id, s32 vol, s32 pan) { return 0; }

// Exchanges the game's copy with the partner's, a word at a time (region 0 first: the slots).
static void Swap(void) {
    u32* body = g_CoopSpikeBody;
    s32 i;
    u32 k, t;

    if (s_Code) {
        u32* ram = (u32*)HDR_ADDR;
        for (k = 0; k < HDR_SIZE / 4; k++) {
            t = ram[k];
            ram[k] = s_Hdr[k];
            s_Hdr[k] = t;
        }
        ram = (u32*)g_api.o.spriteBanks + 16;
        for (k = 0; k < 4; k++) {
            t = ram[k];
            ram[k] = s_Banks[k];
            s_Banks[k] = t;
        }
    }
    // the 64 player slots: only those in use on either side (most are empty)
    for (i = 0; i < 64; i++, body += 0xBC / 4) {
        u32* ram = (u32*)&g_Entities[i];
        if (i && !((Entity*)ram)->entityId && !((Entity*)body)->entityId) { // slot 0 (PLAYER) has id 0
            continue;
        }
        for (k = 0; k < 0xBC / 4; k++) {
            t = ram[k];
            ram[k] = body[k];
            body[k] = t;
        }
    }
    for (i = 1; i < LEN(s_Regions); i++) {
        u32* ram = (u32*)s_Regions[i].addr;
        for (k = 0; k < s_Regions[i].len / 4; k++) {
            t = ram[k];
            ram[k] = *body;
            *body++ = t;
        }
    }
}

static void SwapIn(void);
static bool PartnerLive(void);
static void SwapOut(void);

// A partner build's 'FAR1' trailer (richter/ric_partner.ld, maria/maria_partner.ld): where the
// BSS starts, so it's kept before the first Make zeroes it. Maria's has a sixth word, her init.
typedef struct {
    u32 magic, nearSize, farSize, bssSize, farAddr;
    void (*init)(u16); // Maria's partner init (coop_maria.c); not in Richter's
} FarTrailer;
static bool Trailer(u32 base, u32 size, u32 words, FarTrailer* out) {
    const FarTrailer* t;

    if (size < words * 4 || size > PARTNER_PLAYER_SIZE) {
        return false;
    }
    t = (const FarTrailer*)(base + ((size - words * 4) & ~3));
    if (t->magic != 0x31524146 || t->farAddr != base + t->nearSize) {
        return false;
    }
    *out = *t;
    if (words < 6) {
        out->init = NULL;
    }
    return true;
}

// The partner's Richter, as CoopBoot read it.
static const FarTrailer* PartnerRic(void) {
    static FarTrailer s_Trailer;

    if (!s_Trailer.magic && !Trailer(PARTNER_RIC_ADDR, g_CoopRicPartnerFile.size, 5, &s_Trailer)) {
        return NULL;
    }
    return &s_Trailer;
}

// The partner's Maria, from her blob (the launcher's, in every game where someone plays her: its
// last part), put where it runs once.
static const FarTrailer* PartnerMar(void) {
    static FarTrailer s_Trailer;
    const CharBlob* b = (const CharBlob*)CHAR_BLOB_ADDR;
    const u32* src;
    u32* dst;
    u32 n;

    if (s_Trailer.magic) {
        return &s_Trailer;
    }
    if (b->magic != CHAR_BLOB_MAGIC || b->character != CHAR_MARIA || !b->partnerSize ||
        b->partnerSize > PARTNER_PLAYER_SIZE) {
        return NULL;
    }
    src = (const u32*)((const u8*)(b + 1) + ((b->ovlSize + 3) & ~3) + ((b->vhSize + 3) & ~3) +
                       ((b->vbSize + 3) & ~3));
    dst = (u32*)PARTNER_MAR_ADDR;
    for (n = (b->partnerSize + 3) / 4; n--;) {
        *dst++ = *src++;
    }
    FlushCache(); // new code (D17)
    if (!Trailer(PARTNER_MAR_ADDR, b->partnerSize, 6, &s_Trailer) || !s_Trailer.init) {
        s_Trailer.magic = 0;
        return NULL;
    }
    return &s_Trailer;
}

static const FarTrailer* PartnerCode(u32 character) {
    return character == CHAR_RICHTER ? PartnerRic() : character == CHAR_MARIA ? PartnerMar() : NULL;
}

// A character's graphics file in VRAM's second bank, where the game puts its own in the first:
// 32 strips of 32x128 for x 0x200-0x3FF, y 0x100-0x1FF (src/dra/cd.c), then palettes 0x100-0x1FF
// (x 0-0xFF, y 0xF0-0xFF).
static void LoadGraphics(const u8* file) {
    RECT r;
    s32 i;

    for (i = 0; i < 0x20; i++) {
        r.x = D_800AC958[i];
        r.y = (i & 2 ? 0x180 : 0x100) | VRAM_BANK;
        r.w = 0x20;
        r.h = 0x80;
        if (i == 0x1A) { // as the game does: its first row is a palette (0x380, 0x180)
            r.y = 0x181 | VRAM_BANK;
            r.h = 0x7F;
        }
        LoadImage(&r, (u_long*)(file + i * 0x2000));
        DrawSync(0);
    }
    r.x = 0;
    r.y = 0xF0 | VRAM_BANK;
    r.w = 0x100;
    r.h = 0x10;
    LoadImage(&r, (u_long*)(file + 0x40000));
    DrawSync(0);
}

// The partner starts as a copy of player 1, a little to the right.
#define DRAW_OFS (64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4)) // g_PlayerDraw in the copy

static void Make(void) {
    u32* body = g_CoopSpikeBody;
    PlayerDraw* draw;
    s32 i;
    u32 k;

    for (i = 0; i < LEN(s_Regions); i++) {
        u32* ram = (u32*)s_Regions[i].addr;
        for (k = 0; k < s_Regions[i].len / 4; k++) {
            *body++ = ram[k];
        }
    }
    ((Entity*)g_CoopSpikeBody)->posX.i.hi += 32;
    s_Char = PartnerLive() ? g_CoopLink.partner.character : CHAR_ALUCARD;
    s_Code = s_Char != CHAR_ALUCARD;
    // A partner build's own uploads always go to the second bank (coop_ric.h): it draws from there.
    s_Banked = s_Code || s_Char != CharacterLoaded();
    s_Reloaded = false;
    s_ScrollX = g_Tilemap.scrollX.i.hi; // for SwapIn: no camera move to apply to the copy
    s_ScrollY = g_Tilemap.scrollY.i.hi;
    if (s_Banked && s_BankLoaded != s_Char) { // before the init: Maria's uploads her palettes
        LoadGraphics((const u8*)FGAME2_ADDR); // Richter's; Maria's runs on it too
        s_BankLoaded = s_Char;
    }
    if (s_Code) { // their own code, started by its own init, with nothing of player 1's
        const FarTrailer* t = PartnerCode(s_Char);
        const u32* hdr = (const u32*)(t->farAddr - t->nearSize);
        u32* bss = (u32*)(t->farAddr + t->farSize);
        u32* banks = (u32*)g_api.o.spriteBanks + 16;

        for (k = 0; k < t->bssSize / 4; k++) { // fresh statics (the trailer is in the first words)
            bss[k] = 0;
        }
        for (k = 0; k < HDR_SIZE / 4; k++) {
            s_Hdr[k] = hdr[k];
        }
        for (k = 0; k < 4; k++) {
            s_Banks[k] = banks[k];
        }
        for (k = 0xBC / 4; k < 64 * 0xBC / 4; k++) { // slots 1-63: player 1's (their primitives too)
            g_CoopSpikeBody[k] = 0;
        }
        SwapIn();
        if (t->init) {
            t->init(0);
        } else {
            ((PlayerOvl*)HDR_ADDR)->D_8013C004(0);
        }
        SwapOut();
    }
    // Its sprites go to VRAM's second bank, where player 1's would be (RenderEntities loads each
    // player-sprite frame into its g_PlayerDraw slot as it draws, and clears its edges): y bit 9
    // for the uploads and fills, texpage bit 14 for the drawing (our SwanStation build:
    // patches/swanstation.patch).
    draw = (PlayerDraw*)((u8*)g_CoopSpikeBody + DRAW_OFS);
    for (i = 0; i < 16; i++, draw++) {
        draw->rect0.y |= VRAM_BANK;
        draw->rect1.y |= VRAM_BANK;
        draw->rect2.y |= VRAM_BANK;
        draw->tpage |= TPAGE_BANK;
    }
    s_Made = true;
}

// Entity positions are on screen (relative to the camera), and the camera moved while the copy
// was out of RAM: its slots move with it, as the game moves its own entities.
static void SwapIn(void) {
    s16 dx = s_ScrollX - g_Tilemap.scrollX.i.hi, dy = s_ScrollY - g_Tilemap.scrollY.i.hi;
    s32 i;

    Swap();
    s_SavedChar = g_CoopCharacter;
    s_SavedRandom = g_randomNext; // the partner's randomness doesn't change our game's
    if (s_Code) {
        g_CoopCharacter = PLAYER_RICHTER; // Maria's code runs as Richter's too (coop_api.h)
        s_SavedSfx = g_api.PlaySfx;
        s_SavedSfxVolPan = g_api.PlaySfxVolPan;
        g_api.PlaySfx = NoSfx;
        g_api.PlaySfxVolPan = NoSfxVolPan;
        GfxBefore();
    }
    for (i = 0; i < 64; i++) {
        if (i == 0 || g_Entities[i].entityId) {
            g_Entities[i].posX.i.hi += dx;
            g_Entities[i].posY.i.hi += dy;
        }
    }
}

// The partner's own status (stats, level, equipment: link.h's CoopStatus, sent by its host) in
// the copy, so it fights and casts as itself. Without it (an older partner), it keeps player 1's.
static void PutStatus(void) {
    const CoopStatus* st = (const CoopStatus*)STATUS_PARTNER_ADDR;
    u8* body = (u8*)g_CoopSpikeBody + 64 * 0xBC;
    s32 i;
    u32 k;

    if (st->magic != STATUS_MAGIC) {
        return;
    }
    for (i = 1; i < LEN(s_Regions); i++) {
        const u8* from = s_Regions[i].addr == STATUS_A ? st->a : s_Regions[i].addr == STATUS_B ? st->b : NULL;
        if (from) {
            for (k = 0; k < s_Regions[i].len; k++) {
                body[k] = from[k];
            }
        }
        body += s_Regions[i].len;
    }
}

bool PartnerWeaponDiffers(s32 hand) {
    const CoopStatus* st = (const CoopStatus*)STATUS_PARTNER_ADDR;

    // equipment[hand] is 4 bytes into the second range (subWeapon first)
    return st->magic != STATUS_MAGIC || *(const u32*)(st->b + 4 + hand * 4) != g_Status.equipment[hand];
}

void PartnerBodyOffset(s16* dx, s16* dy) {
    const Entity* body = (const Entity*)g_CoopSpikeBody;

    *dx = body->posX.i.hi + s_ScrollX - g_CoopLink.partner.x;
    *dy = body->posY.i.hi + s_ScrollY - g_CoopLink.partner.y;
}

static void SwapOut(void) {
    s_ScrollX = g_Tilemap.scrollX.i.hi;
    s_ScrollY = g_Tilemap.scrollY.i.hi;
    if (s_Code) {
        GfxAfter();
        g_api.PlaySfx = s_SavedSfx;
        g_api.PlaySfxVolPan = s_SavedSfxVolPan;
    }
    g_CoopCharacter = s_SavedChar;
    g_randomNext = s_SavedRandom;
    Swap();
}

static bool PartnerLive(void) { return g_CoopLink.partnerAge <= PARTNER_STALE_FRAMES; }

// The partner is in this room, in play, as a character we can run: Alucard in an Alucard game
// (DRA's code: another character's game has no Alucard graphics to give it yet), Richter or Maria
// in any (their partner builds).
static bool PartnerHere(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    return p->stage == g_StageId && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top &&
           (p->flags & PRESENCE_IN_PLAY) && g_PlayableCharacter == 0 &&
           ((p->character == CHAR_ALUCARD && CharacterLoaded() == CHAR_ALUCARD) || PartnerCode(p->character));
}

// The body's primitives (its entities' chains), for its own drawing pass. Up to PRIMS of them.
#define PRIMS 96
static s16 s_Prims[PRIMS];
static u8 s_PrimHidden[PRIMS]; // hidden by us from the game's pass (it hadn't hidden it itself)
static s32 s_PrimCount;

static void FindPrims(void) {
    Primitive* prim;
    s32 i;

    s_PrimCount = 0;
    for (i = 0; i < 64; i++) {
        if ((i == 0 || g_Entities[i].entityId) && g_Entities[i].flags & FLAG_HAS_PRIMS) {
            for (prim = &g_PrimBuf[g_Entities[i].primIndex]; prim && s_PrimCount < PRIMS; prim = prim->next) {
                s_Prims[s_PrimCount++] = prim - g_PrimBuf;
            }
        }
    }
}

// Back as the body left them, before its frame (hidden from the game's pass after its own).
static void ShowPrims(void) {
    s32 i;

    for (i = 0; i < s_PrimCount; i++) {
        if (s_PrimHidden[i]) {
            g_PrimBuf[s_Prims[i]].drawMode &= ~DRAW_HIDE;
        }
    }
    s_PrimCount = 0;
}

// The body leaves: its primitives go back to the game, unless a stage load freed them all.
static void Drop(void) {
    s32 i;

    if (s_Made && !s_Reloaded) {
        ShowPrims();
        SwapIn();
        for (i = 0; i < 64; i++) {
            if ((i == 0 || g_Entities[i].entityId) && g_Entities[i].flags & FLAG_HAS_PRIMS) {
                g_api.FreePrimitives(g_Entities[i].primIndex);
                g_Entities[i].flags &= ~FLAG_HAS_PRIMS;
            }
        }
        SwapOut();
    }
    s_Made = false;
    s_PrimCount = 0;
}

bool PartnerSimulated(void) {
    return s_Made && (g_CoopOptions & OPT_PARTNER_SIM) && (!PartnerLive() || PartnerHere());
}

void PartnerFrame(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    Pad pad0;
    Entity* cur;
    s32 t0;
    u16 pad;

    if (g_GameState != Game_Play) {
        s_Reloaded = true;
    }
    if (!(g_CoopOptions & OPT_PARTNER_SIM) || g_GameState != Game_Play || g_GameStep != Play_Default) {
        return;
    }
    if (s_Made && PartnerLive() && (!PartnerHere() || g_CoopLink.partner.character != s_Char)) {
        Drop(); // gone from this room: made again where they are when they're back
    }
    if (PartnerLive() && !PartnerHere()) {
        return;
    }
    if (!s_Made) {
        Make();
        s_ScrollX = g_Tilemap.scrollX.i.hi;
        s_ScrollY = g_Tilemap.scrollY.i.hi;
        if (PartnerLive()) { // where they are (their presence is in room pixels)
            ((Entity*)g_CoopSpikeBody)->posX.i.hi = p->x - g_Tilemap.scrollX.i.hi;
            ((Entity*)g_CoopSpikeBody)->posY.i.hi = p->y - g_Tilemap.scrollY.i.hi;
        }
    }
    pad = PartnerLive() ? g_CoopLink.partnerPad : g_CoopSpikePad;
    t0 = VSync(1);
    if (PartnerLive()) {
        PutStatus();
    }
    ShowPrims();
    SwapIn();
    if (PartnerLive()) { // pulled to their real spot when it drifts
        s16 x = p->x - g_Tilemap.scrollX.i.hi, y = p->y - g_Tilemap.scrollY.i.hi;
        if (PLAYER.posX.i.hi - x > SNAP_PX || x - PLAYER.posX.i.hi > SNAP_PX ||
            PLAYER.posY.i.hi - y > SNAP_PX || y - PLAYER.posY.i.hi > SNAP_PX) {
            PLAYER.posX.i.hi = x;
            PLAYER.posY.i.hi = y;
            PLAYER.velocityX = PLAYER.velocityY = 0;
        }
    }
    pad0 = g_pads[0];
    g_pads[0].pressed = pad;
    g_pads[0].tapped = pad & ~s_PrevPad;
    g_pads[0].repeat = g_pads[0].tapped;
    s_PrevPad = pad;
    cur = g_CurrentEntity;
    g_CurrentEntity = &PLAYER;
    if (s_Code) { // as DRA runs Richter's (src/dra/5087C.c)
        ((PlayerOvl*)HDR_ADDR)->D_8013C000();
        ((PlayerOvl*)HDR_ADDR)->D_8013C008();
    } else {
        EntityAlucard();
        UpdatePlayerEntities();
    }
    g_CurrentEntity = cur;
    g_pads[0] = pad0;
    SwapOut();
    g_CoopSpikeLines = (u16)(VSync(1) - t0); // a 16-bit counter
    if (g_CoopSpikeLines > g_CoopSpikeMax) {
        g_CoopSpikeMax = g_CoopSpikeLines;
    }
}

// The body's own hand-weapon entities (DRA runs ids 0xE0-0xEF from hand 0's overlay, 0xF0-0xFF
// from hand 1's) when the weapon isn't ours: not drawn (weapons.c draws the real swing).
static bool HiddenWeapon(const Entity* e) {
    return !s_Code && e->entityId >= 0xE0 && PartnerWeaponDiffers(e->entityId >= 0xF0);
}

// What the body just drew, from its character's graphics in the second bank: textures in
// F_GAME's pages (x 0x200-0x3FF, y 0x100-0x1FF) and palettes in its rows (x 0-0xFF, y 0xF0-0xFF).
static u16 BankTpage(u16 t) { return (t & 0xF) >= 8 && (t & 0x10) ? t | TPAGE_BANK : t; }
static u16 BankClut(u16 c) {
    u16 y = (c >> 6) & 0x1FF;
    return y >= 0xF0 && y < 0x100 && (c & 0x3F) < 0x10 ? c | CLUT_BANK : c;
}

static void BankPolys(u32 gt4, u32 gt3) {
    for (; gt4 < g_GpuUsage.gt4; gt4++) {
        g_CurrentBuffer->polyGT4[gt4].tpage = BankTpage(g_CurrentBuffer->polyGT4[gt4].tpage);
        g_CurrentBuffer->polyGT4[gt4].clut = BankClut(g_CurrentBuffer->polyGT4[gt4].clut);
    }
    for (; gt3 < g_GpuUsage.gt3; gt3++) {
        g_CurrentBuffer->polyGT3[gt3].tpage = BankTpage(g_CurrentBuffer->polyGT3[gt3].tpage);
        g_CurrentBuffer->polyGT3[gt3].clut = BankClut(g_CurrentBuffer->polyGT3[gt3].clut);
    }
}

// The body's primitives, drawn now by themselves (every other one hidden for it), then hidden
// from the game's pass (ShowPrims puts them back before the body's next frame).
static void DrawPrims(void) {
    static u8 s_Others[MAX_PRIM_COUNT]; // DRAW_HIDE we set on others for our pass
    u32 gt4 = g_GpuUsage.gt4, gt3 = g_GpuUsage.gt3;
    s32 i;

    FindPrims();
    if (!s_PrimCount) {
        return;
    }
    for (i = 0; i < MAX_PRIM_COUNT; i++) {
        s_Others[i] = !(g_PrimBuf[i].drawMode & DRAW_HIDE);
        g_PrimBuf[i].drawMode |= DRAW_HIDE;
    }
    for (i = 0; i < s_PrimCount; i++) {
        if (s_Others[s_Prims[i]]) {
            g_PrimBuf[s_Prims[i]].drawMode &= ~DRAW_HIDE;
        }
    }
    RenderPrimitives();
    if (s_Banked) {
        BankPolys(gt4, gt3);
    }
    for (i = 0; i < MAX_PRIM_COUNT; i++) {
        if (s_Others[i]) {
            g_PrimBuf[i].drawMode &= ~DRAW_HIDE;
        }
    }
    for (i = 0; i < s_PrimCount; i++) {
        s_PrimHidden[i] = s_Others[s_Prims[i]];
        g_PrimBuf[s_Prims[i]].drawMode |= DRAW_HIDE;
    }
}

// Draws the partner: its slots swapped in, everything else hidden (animCurFrame 0, which
// RenderEntities skips), drawn, and all put back. After player 1's RenderEntities.
void PartnerDraw(void) {
    static u16 frames[256];
    s32 i;

    if (!PartnerSimulated() || g_GameState != Game_Play) {
        return;
    }
    u32 gt4 = g_GpuUsage.gt4, gt3 = g_GpuUsage.gt3;

    SwapIn();
    for (i = 1; i < 256; i++) {
        frames[i] = g_Entities[i].animCurFrame;
        if (i >= 64 || HiddenWeapon(&g_Entities[i])) {
            g_Entities[i].animCurFrame = 0;
        }
    }
    RenderEntities();
    for (i = 1; i < 256; i++) {
        g_Entities[i].animCurFrame = frames[i];
    }
    if (s_Banked) {
        BankPolys(gt4, gt3);
    }
    if (s_Code) { // its whip and effects (most of Richter's attacks are primitives)
        DrawPrims();
    }
    SwapOut();
}

// Where the partner is (the harness checks it moves as its buttons say).
const Entity* PartnerBody(void) { return s_Made ? (const Entity*)g_CoopSpikeBody : NULL; }
