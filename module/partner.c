// M13 (design/M13-partner-player.md): the partner as a real second player. Each frame, after the
// game has updated player 1, the partner's copy of "the player" is swapped into RAM, the game's
// own player update runs on it with the partner's buttons (CoopLink.partnerPad, played out with
// its presence), and it's swapped back out. It exists while the partner is in our room, and is
// pulled to their real spot when it drifts past SNAP_PX. Cosmetic: no hit detection runs for it.
// Off unless OPT_PARTNER_SIM is set (not finished: Alucard partners only, no VRAM bank yet).
// Without a partner (the harness's spike test), it's a copy of player 1 on g_CoopSpikePad.
#define COOP_MODULE
#include <game.h>
#include "coop_api.h"
#include "link.h"
#include "partner.h"
#include "puppet.h"

void EntityAlucard(void);        // DRA
void UpdatePlayerEntities(void); // DRA
void RenderEntities(void);       // DRA

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
    {0x80097BA0, 0x48},                 // g_Status: hp .. statsTotal
    {0x80097BFC, 0x34},                 // g_Status: subWeapon .. elements
    {0x8013796C, 0x30},                 // g_PlayerHud
    {0x80139828, 0x40},                 // g_StatBuffTimers
    {0x80138FC0, 0x40},                 // g_ButtonCombo
};
#define BODY_SIZE (64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4) + 0x280 + 8 + 4 + 0x48 + 0x34 + 0x30 + 0x40 + 0x40)
u32 g_CoopSpikeBody[BODY_SIZE / 4]; // the partner's copy, while player 1's is in RAM (its entity 0 first)
static bool s_Made;
static u16 s_PrevPad;
static s16 s_ScrollX, s_ScrollY; // the camera when the copy was last swapped out
#define SNAP_PX 48

u32 g_CoopSpikePad;   // harness: the partner's buttons (PAD_*)
u32 g_CoopSpikeLines; // the last partner frame's cost, in scanlines (263 a frame)
u32 g_CoopSpikeMax;   // the most it has cost

// Exchanges the game's copy with the partner's, a word at a time (region 0 first: the slots).
static void Swap(void) {
    u32* body = g_CoopSpikeBody;
    s32 i;
    u32 k, t;

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
    // Its sprites upload one VRAM page to the left of player 1's (RenderEntities loads each
    // player-sprite frame into its g_PlayerDraw slot as it draws): the old puppet's page
    // (puppet.c, 0x1C1,0x101), free while the partner is simulated.
    draw = (PlayerDraw*)((u8*)g_CoopSpikeBody + DRAW_OFS);
    for (i = 0; i < 16; i++, draw++) {
        draw->rect0.x -= 0x40;
        draw->rect1.x -= 0x40;
        draw->rect2.x -= 0x40;
        draw->tpage -= 1;
    }
    s_Made = true;
}

// Entity positions are on screen (relative to the camera), and the camera moved while the copy
// was out of RAM: its slots move with it, as the game moves its own entities.
static void SwapIn(void) {
    s16 dx = s_ScrollX - g_Tilemap.scrollX.i.hi, dy = s_ScrollY - g_Tilemap.scrollY.i.hi;
    s32 i;

    Swap();
    for (i = 0; i < 64; i++) {
        if (i == 0 || g_Entities[i].entityId) {
            g_Entities[i].posX.i.hi += dx;
            g_Entities[i].posY.i.hi += dy;
        }
    }
}

static void SwapOut(void) {
    s_ScrollX = g_Tilemap.scrollX.i.hi;
    s_ScrollY = g_Tilemap.scrollY.i.hi;
    Swap();
}

static bool PartnerLive(void) { return g_CoopLink.partnerAge <= PARTNER_STALE_FRAMES; }

// The partner is in this room, in play, as Alucard (other characters: the VRAM bank, later).
static bool PartnerHere(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    return p->stage == g_StageId && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top &&
           (p->flags & PRESENCE_IN_PLAY) && p->character == 0 && g_PlayableCharacter == 0;
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

    if (!(g_CoopOptions & OPT_PARTNER_SIM) || g_GameState != Game_Play || g_GameStep != Play_Default) {
        return;
    }
    if (PartnerLive() && !PartnerHere()) {
        s_Made = false; // gone from this room: made again where they are when they're back
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
    EntityAlucard();
    UpdatePlayerEntities();
    g_CurrentEntity = cur;
    g_pads[0] = pad0;
    SwapOut();
    g_CoopSpikeLines = (u16)(VSync(1) - t0); // a 16-bit counter
    if (g_CoopSpikeLines > g_CoopSpikeMax) {
        g_CoopSpikeMax = g_CoopSpikeLines;
    }
}

// Draws the partner: its slots swapped in, everything else hidden (animCurFrame 0, which
// RenderEntities skips), drawn, and all put back. After player 1's RenderEntities.
void PartnerDraw(void) {
    static u16 frames[256 - 64];
    s32 i;

    if (!PartnerSimulated() || g_GameState != Game_Play) {
        return;
    }
    SwapIn();
    for (i = 64; i < 256; i++) {
        frames[i - 64] = g_Entities[i].animCurFrame;
        g_Entities[i].animCurFrame = 0;
    }
    RenderEntities();
    for (i = 64; i < 256; i++) {
        g_Entities[i].animCurFrame = frames[i - 64];
    }
    SwapOut();
}

// Where the partner is (the harness checks it moves as its buttons say).
const Entity* PartnerBody(void) { return s_Made ? (const Entity*)g_CoopSpikeBody : NULL; }
