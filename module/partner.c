// M13 (design/M13-partner-player.md): the partner as a real second player. Each frame, after the
// game has updated player 1, the partner's copy of "the player" is swapped into RAM, the game's
// own player update runs on it with the partner's buttons (CoopLink.partnerPad, played out with
// its presence), and it's swapped back out. It exists while the partner is in our room, and is
// eased back to their real spot when it drifts (put there past SNAP_PX). Cosmetic: no hit detection runs for it.
// It's how the partner is drawn (M13 step 5: the puppet is gone). Without a partner, there's no
// body, except in the harness's spike test (OPT_PARTNER_SIM): a copy of player 1 on g_CoopSpikePad.
//
// A Richter partner (step 3) runs our Richter linked to run there (PARTNER_RIC_ADDR,
// characters/richter-ps1/ric_partner.ld), with statics of its own: for its frame, its g_PlOvl table and sprite
// table go into 0x8013C000 (where DRA looks), its sprite banks into g_api.o.spriteBanks[16..19],
// and the character to Richter's. In another character's game, its graphics (F_GAME2.BIN) are in
// VRAM's second bank, and what it draws reads them there (BankPolys).
#define COOP_MODULE
#include <game.h>
#include "coop_api.h"
#include "link.h"
#include "partner.h"
#include "character.h"
#include "familiar.h"
#include "arrive.h"
#include <sfx.h>

void EntityAlucard(void);        // DRA
void UpdatePlayerEntities(void); // DRA
void RenderEntities(void);       // DRA
void RenderPrimitives(void);     // DRA
u32 CharacterLoaded(void);       // character.c
void FlushCache(void);           // main.exe (PsyQ)
void AluInit(void);              // DRA
void DestroyEntity(Entity* e);   // DRA
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
    {STATUS_A, STATUS_A_SIZE},          // g_Status: spellsLearnt .. statsTotal (the partner's: PutStatus)
    {STATUS_B, STATUS_B_SIZE},          // g_Status: subWeapon .. elements
    {0x8013796C, 0x30},                 // g_PlayerHud
    {0x80139828, 0x40},                 // g_StatBuffTimers
    {0x80138FC0, 0x40},                 // g_ButtonCombo
    // DRA statics the player code also keeps (M13 step 5: a partner's Alucard used player 1's, and
    // a guest's attack stopped landing), outside the other project's list. Not D_80139A7C (5KB): an
    // effect's image, stored and loaded again within that effect.
    {0x80137960, 0xC},                  // D_80137960-D_80137968 (5D5BC.c's timers)
    {0x801396E4, 0x8},                  // D_801396E4, D_801396E8
    {0x801396F8, 0x100},                // D_801396F8, D_80139778 (AluInit's afterimage tables)
    {0x80139824, 0x4},                  // D_80139824
    {0x8013AECC, 0x4},                  // D_8013AECC
    {0x8013AEE4, 0x4},                  // D_8013AEE4
    {0x80097BF8, 0x4},                  // g_Status.D_80097BF8 (bit 0: no MP back), between the two ranges
};
#define BODY_SIZE (64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4) + 0x280 + 8 + 4 + STATUS_A_SIZE + 0x34 + 0x30 + 0x40 + 0x40 + \
                   0xC + 0x8 + 0x100 + 0x4 + 0x4 + 0x4 + 0x4)

// A partner who runs its own player code (Richter, Maria), or an Alucard partner in their game:
// what DRA reads at 0x8013C000 (g_PlOvl: the update functions, then the body's sprite table, which
// ends at 0x8013C334 in our Richter's file and 0x8013C388 in Alucard's ARC_F.BIN) and the four
// sprite banks a Richter or Maria init installs. Swapped with player 1's for its frames.
#define HDR_ADDR 0x8013C000
#define HDR_SIZE 0x388
// Saturn Maria's sprite table is longer (0x568 bytes, to 0x8013C588), and her code rewrites it as
// it unpacks her images: her partner's header is that much, taken again at each swap-in
#define HDR_SIZE_SAT 0x588
#define BANKS 8 // sprite banks 0x10-0x17: Richter's 0x10-0x13, Maria's 0x10-0x16, the off-hand's 0x17
// M17 step 4: one body per partner (partner k: CoopLink's partner for 0, more[k - 1] after), each
// with everything that was this file's one body. B is the body whose turn it is (s_K its partner).
#define PRIMS 96     // its primitives, up to (its own drawing: FindPrims)
#define FLASHES 8    // its screen flashes, hidden (HideFlashes)
#define ALU_SHEETS 218
#define ALU_BATS 6
typedef struct {
    u32 hdr[HDR_SIZE_SAT / 4];
    u32 hdrWords;
    const u32* liveHdr; // Saturn Maria's partner build's own header, which her code writes to
    u32 banks[BANKS];
    u32 chr;            // CHAR_* of the body
    bool code;          // it runs its own player code (not DRA's Alucard)
    bool aluHere;       // an Alucard partner in another character's game (DRA's Alucard, ARC_F swapped in)
    bool otherChar;     // another character than player 1 (its own afterimage slots: Swap)
    bool banked;        // its graphics are in its VRAM bank (another character than ours)
    bool reloaded;      // the stage reloaded since Make (its primitives are gone with it)
    bool made;
    bool justMade;      // made this frame: its update and drawing start next frame
    bool teleportSeen;  // the partner's FLIP_TELEPORT_IN, last frame
    bool bodyDied;      // dead here while the partner isn't: made again
    u8 bank;            // its VRAM bank (M17: partner k's is k + 1)
    u8 formApart;
    u16 prevPad;
    s16 scrollX, scrollY; // the camera when the copy was last swapped out
    s16 driftFrames;
    u32 bankLoaded;     // CHAR_* whose graphics are in its bank (0xFF: none)
    u32 partnerSeed;
    s32 partnerHp;      // its HP, as its status last said (a drop: it was hit in its game)
    Unkstruct_8006C3C4 palOps[LEN(D_8006C3C4)]; // DRA's palette operations, kept from it
    u32 aluBats[ALU_BATS];
    s16 prims[PRIMS];
    u8 primHidden[PRIMS]; // hidden by us from the game's pass (it hadn't hidden it itself)
    s32 primCount;
    s16 flash[FLASHES];
    s32 flashCount;
    u32 wpnSeq[2];   // #343: the partner's weapon copy (link.h CoopWeapon.seq) its own copy is of
    bool wpnRun[2];  // this frame it runs that hand's weapon itself (BodyWeapons)
    u16 wpnClutSum[2]; // its palettes as last put in its bank
} Body;
static Body s_Bodies[COOP_PARTNERS];
static Body* B = s_Bodies;
static s32 s_K; // B's partner
static bool s_BodiesSet;
// Each body's rollback (RollFrame, below)
typedef struct {
    bool on;
    u32 s;  // the last frame the body ran
    u32 lo; // the oldest frame with a snapshot (the ring holds lo..s)
    s32 hit; // a hit that came while the body had no frame to run: given with its next
    s16 driftFrames;
    s16 drawX, drawY;   // a rollback's correction, still to slide out: drawn this far from the body
    s16 shiftX, shiftY; // its primitives were moved this much for the game's pass (DrawShift)
} Roll;
static Roll s_Roll[COOP_PARTNERS];

static void SetBodies(void) {
    s32 k;

    for (k = 0; k < COOP_PARTNERS; k++) {
        s_Bodies[k].hdrWords = HDR_SIZE / 4;
        s_Bodies[k].bankLoaded = 0xFF;
        s_Bodies[k].partnerSeed = 1;
        s_Bodies[k].partnerHp = -1;
        s_Bodies[k].bank = k + 1;
    }
    s_BodiesSet = true;
}

// Partner s_K's side of the link
static const CoopPresence* Presence(void) {
    return s_K ? &g_CoopLink.more[s_K - 1].presence : &g_CoopLink.partner;
}
static u32 Age(void) { return s_K ? g_CoopLink.more[s_K - 1].age : g_CoopLink.partnerAge; }
static u32 PadIn(void) { return s_K ? g_CoopLink.more[s_K - 1].pad : g_CoopLink.partnerPad; }
static const CoopStatus* StatusIn(void) {
    return (const CoopStatus*)(s_K ? STATUS_MORE_ADDR(s_K) : STATUS_PARTNER_ADDR);
}

static s32 s_SavedChar;
static u32 s_SavedRandom;
CdlFILE g_CoopRicPartnerFile; // CoopBoot: COOPRICP.BIN (coop_api.h)
extern u32 g_randomNext; // DRA's Random()

// The partner's rand(): main.exe's rand() is the BIOS's, its seed somewhere in the BIOS's memory.
// Found once (FindRandSeed: two calls, and the word in kernel RAM that gives both, by the C
// library's generator; then put back as it was), it's the partner's own for its frames, so the
// partner's effects never change player 1's enemies (they showed in boss fights: M13 step 5).
#define RAND_A 1103515245u
#define RAND_C 12345u
#define RAND_A_INV 0xEEB9EB65u // RAND_A * RAND_A_INV == 1 (mod 2^32)
int rand(void); // main.exe
u32* g_CoopRandSeed;        // the BIOS's seed (NULL: not found, so not kept; tests read it)
static bool s_RandLooked;

// Once, at boot (coop.c: its first frame, while the logos show): a 64KB scan is too slow for a
// frame of play (the first body's frame lagged a frame, and player 1 with it).
void PartnerBoot(void) {
    u32 x, y, s1, s0, *w;

    if (s_RandLooked) {
        return;
    }
    s_RandLooked = true;
    for (x = 0; x < COOP_PARTNERS - 1; x++) { // the partners after the first: none yet (boss.c counts them)
        g_CoopLink.more[x].age = 0xFFFF;
    }
    x = rand();
    y = rand();
    for (w = (u32*)0x80000000; w < (u32*)0x80010000; w++) {
        if (((*w >> 16) & 0x7FFF) != y) {
            continue;
        }
        s1 = (*w - RAND_C) * RAND_A_INV;
        if (((s1 >> 16) & 0x7FFF) == x) {
            s0 = (s1 - RAND_C) * RAND_A_INV;
            *w = s0; // as before the two calls
            g_CoopRandSeed = w;
            return;
        }
    }
}

static void RandOff(void) {
    u32 t;

    if (g_CoopRandSeed) {
        t = *g_CoopRandSeed;
        *g_CoopRandSeed = B->partnerSeed;
        B->partnerSeed = t;
    }
}

static void RandOn(void) {
    u32 t;

    if (g_CoopRandSeed) {
        t = *g_CoopRandSeed;
        *g_CoopRandSeed = B->partnerSeed;
        B->partnerSeed = t;
    }
}
u32 g_CoopSpikeBody[COOP_PARTNERS][BODY_SIZE / 4]; // each partner's copy, while player 1's is in RAM (its entity 0 first)
#define BODY_BUF g_CoopSpikeBody[s_K]
#define SNAP_PX 96   // further than this from its real spot: put there (#291: 48 was a running Richter's knockback)
#define DRIFT_PX 8   // nearer than this: left alone (the link's lag; its own code moves it)
#define DRIFT_FRAMES 60 // off for longer than this (a second), easing back: put there

// A frame's pull back toward the real spot: an eighth of the way, at least a pixel, none when near.
static s32 Ease(s32 d) {
    if (d <= DRIFT_PX && d >= -DRIFT_PX) {
        return 0;
    }
    return d / 8 ? d / 8 : (d > 0 ? 1 : -1);
}

u32 g_CoopSpikePad;   // harness: the partner's buttons (PAD_*)
u32 g_CoopSpikeLines; // the last partner frame's cost, in scanlines (263 a frame)
u32 g_CoopSpikeMax;   // the most it has cost
u32 g_CoopMakeLines;  // what making the body last cost, in scanlines (tests)
static bool s_AfterLoad; // a load, its Engine_Init not run yet: no body

// The game's one copy of each hand weapon's overlay (0x8017A000, 0x8017D000) and of the familiar's
// (0x80170000) is player 1's, with statics of its own: the body never runs them (its weapon code
// would change player 1's swing: a guest's weapon stopped spawning). For its frames the weapons'
// tables point at nothing, and so does the module's off-hand entry (offhand.c, g_CoopWeaponEntity,
// for Richter's and Maria's); its weapon and familiar entities are taken out after its update.
// Its hand weapons' swings are drawn from the link instead (weapons.c), the familiar's too.
extern void (*g_CoopWeaponEntity)(Entity*); // coop_api.h's fixed table
#define WEAPON_HDR(hand) ((u32*)((hand) ? 0x8017D000 : 0x8017A000))
#define WEAPON_HDR_WORDS (0x40 / 4) // its Weapon table (include/weapon.h)
static void NoWeapon(void) {}
static s32 NoWeaponId(void) { return 0; }
static u32 s_WeaponHdr[2][WEAPON_HDR_WORDS];
static void (*s_WeaponEntity)(Entity*);

// #343: an Alucard body runs its partner's own hand weapons, so its swings come with its attacks
// (they came from the partner's game, at the network's delay, after the body's attack started).
// The game's one copy of each weapon's program (0x8017A000, 0x8017D000) is player 1's: for the
// body's frame it's exchanged with the body's own (made from the partner's copy, link.h
// CoopWeapon), and so is that hand's 24 palettes in g_Clut. Its sheet and palettes are in the
// body's VRAM bank, where what it draws reads them. Not while the disc is busy: player 1's own
// weapon may be on its way in (it would land in the body's copy).
static bool PartnerLive(void);
static void CopyWords(void* dst, const void* src, u32 len);
static void ExchangeWords(void* a, void* b, u32 len);
#define CD_IDLE 0 // CdStep_None (include/disk.h)
#define BODY_WEAPON(k, hand) ((u32*)(0x80F00000 + ((k) * 2 + (hand)) * 0x3400)) // its program, then palettes
#define BODY_WPN_OVL 0x3000
#define BODY_WPN_CLUT 0x300
#define WEAPON_ADDR(hand) ((u32*)((hand) ? 0x8017D000 : 0x8017A000))
#define WEAPON_SHEET_X 0x240
#define WEAPON_SHEET_Y(hand) ((hand) ? 0x180 : 0x100)
#define WEAPON_PALS 0x110
u32 g_CoopBodyWeaponFrames; // body frames run with a weapon of its own (tests read it: coop.map)
static const CoopWeapon* PartnerWeapon(s32 hand) {
    return (const CoopWeapon*)(s_K ? WEAPON_MORE_ADDR(s_K, hand) : WEAPON_PARTNER_ADDR + hand * WEAPON_HAND_SIZE);
}
static u16* ClutOfHand(s32 hand) { return (u16*)g_Clut + (WEAPON_PALS + hand * 24) * COLORS_PER_PAL; }
static u16 Sum(const u16* p, s32 n) {
    u16 x = 0;
    while (n--) {
        x = (x << 1 | x >> 15) ^ *p++;
    }
    return x;
}
static void BankPalettes(s32 hand, const u16* clut) {
    RECT r;
    s32 i;
    u16 c;

    for (i = 0; i < 24; i++) {
        c = g_ClutIds[WEAPON_PALS + hand * 24 + i];
        r.x = (c & 0x3F) * 16;
        r.y = ((c >> 6) & 0x1FF) | VRAM_BANK_OF(B->bank);
        r.w = 16;
        r.h = 1;
        LoadImage(&r, (u_long*)(clut + i * 16));
    }
    B->wpnClutSum[hand] = Sum(clut, BODY_WPN_CLUT / 2);
}
static void BodyWeaponsIn(void) {
    const CoopWeapon* w;
    RECT r;
    s32 hand, i;

    for (hand = 0; hand < 2; hand++) {
        w = PartnerWeapon(hand);
        B->wpnRun[hand] = !B->code && PartnerLive() && w->magic == WEAPON_MAGIC &&
                          w->item == g_Status.equipment[hand] && !g_IsUsingCd && g_CdStep == CD_IDLE;
        if (!B->wpnRun[hand]) {
            continue;
        }
        if (B->wpnSeq[hand] != w->seq) { // a new weapon: its own copy, sheet and palettes
            CopyWords(BODY_WEAPON(s_K, hand), w->ovl, BODY_WPN_OVL);
            CopyWords(BODY_WEAPON(s_K, hand) + BODY_WPN_OVL / 4, w->clut, BODY_WPN_CLUT);
            r.x = WEAPON_SHEET_X;
            r.y = WEAPON_SHEET_Y(hand) | VRAM_BANK_OF(B->bank);
            r.w = 0x40;
            r.h = 0x80;
            LoadImage(&r, (u_long*)w->sheet);
            BankPalettes(hand, w->clut);
            for (i = 1; i < 64; i++) { // the last weapon's entities are gone with it
                if ((g_Entities[i].entityId & 0xF0) == 0xE0 + hand * 0x10) {
                    DestroyEntity(&g_Entities[i]);
                }
            }
            B->wpnSeq[hand] = w->seq;
        }
        ExchangeWords(WEAPON_ADDR(hand), BODY_WEAPON(s_K, hand), BODY_WPN_OVL);
        ExchangeWords(ClutOfHand(hand), BODY_WEAPON(s_K, hand) + BODY_WPN_OVL / 4, BODY_WPN_CLUT);
    }
    g_CoopBodyWeaponFrames += B->wpnRun[0] || B->wpnRun[1];
}
static void BodyWeaponsOut(void) {
    const u16* clut;
    s32 hand;

    for (hand = 0; hand < 2; hand++) {
        if (!B->wpnRun[hand]) {
            continue;
        }
        ExchangeWords(WEAPON_ADDR(hand), BODY_WEAPON(s_K, hand), BODY_WPN_OVL);
        ExchangeWords(ClutOfHand(hand), BODY_WEAPON(s_K, hand) + BODY_WPN_OVL / 4, BODY_WPN_CLUT);
        clut = (const u16*)(BODY_WEAPON(s_K, hand) + BODY_WPN_OVL / 4);
        if (Sum(clut, BODY_WPN_CLUT / 2) != B->wpnClutSum[hand]) { // its code changed its colours
            BankPalettes(hand, clut);
        }
    }
}

static void WeaponsOff(void) {
    s32 hand, k;

    for (hand = 0; hand < 2; hand++) {
        if (B->wpnRun[hand]) { // its own (BodyWeaponsIn)
            continue;
        }
        for (k = 0; k < WEAPON_HDR_WORDS; k++) {
            s_WeaponHdr[hand][k] = WEAPON_HDR(hand)[k];
            WEAPON_HDR(hand)[k] = (u32)(k == 6 ? (void*)NoWeaponId : (void*)NoWeapon); // 6: GetWeaponId
        }
    }
    s_WeaponEntity = g_CoopWeaponEntity;
    g_CoopWeaponEntity = (void (*)(Entity*))NoWeapon;
}

// Only the words still stubbed: a weapon's program the disc finished loading during the body's
// frame (the off-hand's, asynchronous) is the new one. Putting the old header back over it, the
// next InitWeapon called a stale LoadWeaponPalette, which wrote through NULL into the BIOS.
static void WeaponsOn(void) {
    s32 hand, k;

    for (hand = 0; hand < 2; hand++) {
        if (B->wpnRun[hand]) {
            continue;
        }
        for (k = 0; k < WEAPON_HDR_WORDS; k++) {
            if (WEAPON_HDR(hand)[k] == (u32)(k == 6 ? (void*)NoWeaponId : (void*)NoWeapon)) {
                WEAPON_HDR(hand)[k] = s_WeaponHdr[hand][k];
            }
        }
    }
    g_CoopWeaponEntity = s_WeaponEntity;
}

// Graphics a partner's own code queues for DRA's loader (Maria's guardians, HUD): their entries
// (its own data) get the body's bank in their y, so the loader puts them there. An
// entry's xy holds y in its low half and x in its high one (LoadPendingGfx passes xy >> 16 as x;
// GFX_ENTRY's first argument is the y). The bit once went in the high half: x bit 9, already set
// for x 0x200 and up, so her HUD and guardians went over player 1's HUD name and sheet (#165).
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
                e->xy = (u_long*)(((u32)e->xy & ~VRAM_BANK_OF(3)) | VRAM_BANK_OF(B->bank));
            }
        }
    }
}

// The partner's sounds (step 4): the requests its frame added to DRA's ring are quieter (the host's
// setting) and panned to where it is. A sound of the player's own bank (VAB 1: Alucard's or
// Richter's and Maria's voice) is another character's here: dropped (volume 0). Its sound
// commands (music, and the XA voices streamed from the disc: Richter's and Maria's) are all
// dropped: they're its game's, and an XA stream takes our drive (a load that started while one
// played read the stream's sectors as the stage's code, and the game jumped into them).
extern s16 g_sfxRingBufferWritePos;            // DRA
extern SfxRingBufferItem g_SfxRingBuffer[0x100]; // DRA
extern Unkstruct_800BF554 g_SfxData[];         // DRA
#define PARTNER_VOL 60 // % of its volume, unless the host says otherwise
#define PLAYER_VAB 1
static s16 s_SfxPos;
static s16 s_CmdPos;
extern s16 g_SoundCommandRingBufferWritePos;  // DRA
extern s16 g_SoundCommandRingBuffer[0x100];  // DRA

static bool s_Again; // the body's frame was run again (rollback, Run): its sounds were heard
// Rollback (Slippi's sound log): each frame run keeps the sounds it asked for. Run again after a
// wrong guess, a frame's sounds that were heard the first time are dropped, and the ones the right
// buttons brought (a swing the guess missed) play.
#define ROLL_SFX 6
typedef struct {
    u8 n;
    u8 pad_[3];
    u16 ids[ROLL_SFX];
} SfxLog;
static SfxLog* s_SfxLog; // the frame being run's (NULL: not rolling)

static void SfxAgain(void) {
    SfxLog old = *s_SfxLog;
    s16 pos, to = s_SfxPos;
    s32 i;
    u16 id;

    s_SfxLog->n = 0;
    for (pos = s_SfxPos; pos != g_sfxRingBufferWritePos; pos = (pos + 1) & 0xFF) {
        id = g_SfxRingBuffer[pos].sndId;
        if (s_SfxLog->n < ROLL_SFX) {
            s_SfxLog->ids[s_SfxLog->n++] = id;
        }
        for (i = 0; i < old.n && old.ids[i] != id; i++) {
        }
        if (s_Again && i < old.n) {
            old.ids[i] = 0xFFFF; // heard: each heard once
            continue;
        }
        g_SfxRingBuffer[to] = g_SfxRingBuffer[pos];
        to = (to + 1) & 0xFF;
    }
    for (pos = to; pos != g_sfxRingBufferWritePos; pos = (pos + 1) & 0xFF) {
        g_SfxRingBuffer[pos].sndId = 0;
    }
    g_sfxRingBufferWritePos = to;
    s_Again = false;
}

// A partner's sound from a bank this game's sound memory holds for its own player (VAB 1: the
// character's; VAB 2: Alucard's familiar, Richter's and Maria's second bank) would play this
// player's sound instead (Alucard's grunt for Richter's whip). Those go to the host, which plays them
// from the partner character's own bank (#344).
static bool SameBank1(u32 a, u32 b) {
    return a == b || ((a == CHAR_RICHTER || a == CHAR_ULT_RICHTER) && (b == CHAR_RICHTER || b == CHAR_ULT_RICHTER));
}
static bool OtherBank(u8 vab) {
    u32 mine = CharacterLoaded();

    if (vab == PLAYER_VAB) {
        return !SameBank1(B->chr, mine);
    }
    if (vab == 2) { // Alucard's is his familiar's; Saturn Maria's is her own; the rest, SD_MAR
        return (B->chr == CHAR_ALUCARD) != (mine == CHAR_ALUCARD) ||
               (B->chr == CHAR_SAT_MARIA) != (mine == CHAR_SAT_MARIA);
    }
    return false;
}
u32 g_CoopSoundsOut; // partner sounds handed to the host (tests read it: coop.map)
static void SoundOut(const Unkstruct_800BF554* d, s32 vol, s32 pan) {
    volatile CoopSfxOut* out = SFX_OUT;
    volatile CoopSfx* s;

    if (out->frame != g_Timer) {
        out->frame = g_Timer;
        out->n = 0;
    }
    if (out->n >= SFX_OUT_MAX) {
        return;
    }
    s = &out->items[out->n++];
    s->chr = B->chr;
    s->vab = d->vabid;
    s->prog = d->prog;
    s->tone = d->tone;
    s->note = d->note;
    s->vol = vol * (d->volume < 0 ? 0 : d->volume) / 127;
    s->pan = pan;
    g_CoopSoundsOut++;
}

static void PartnerSounds(void) {
    s32 pct = (g_CoopLink.control >> CONTROL_PARTNER_VOL_SHIFT) & 0xFF, vol, pan;
    SfxRingBufferItem* it;
    s16 pos;

    pct = pct ? pct : PARTNER_VOL;
    pan = (PLAYER.posX.i.hi - 128) / 16;
    pan = pan < -8 ? -8 : pan > 8 ? 8 : pan;
    for (pos = s_CmdPos; pos != g_SoundCommandRingBufferWritePos; pos = (pos + 1) & 0xFF) {
        g_SoundCommandRingBuffer[pos] = 0;
    }
    g_SoundCommandRingBufferWritePos = s_CmdPos;
    if (s_SfxLog) {
        SfxAgain();
    }
    s_Again = false;
    for (pos = s_SfxPos; pos != g_sfxRingBufferWritePos; pos = (pos + 1) & 0xFF) {
        it = &g_SfxRingBuffer[pos];
        vol = it->sndVol == 0xFFFF ? 0x7F : it->sndVol;
        vol = (vol * pct / 100) & 0x7F;
        if (OtherBank(g_SfxData[it->sndId].vabid)) { // not in our sound memory: the host plays it
            SoundOut(&g_SfxData[it->sndId], vol, pan);
            it->sndVol = 0;
            continue;
        }
        it->sndVol = vol;
        it->sndPan = pan;
    }
}

// Our SwanStation's copy engine (patches/swanstation.patch, at 0x1F802100): a copy or an exchange
// of whole words in a few cycles, where the CPU's own loop takes some 9 a word (the snapshots of
// rollback, below, and Swap). Without it (another emulator), the CPU's loop.
#define COPY_REGS ((volatile u32*)0x1F802100)
#define COPY_MAGIC 0x59504F43 // 'COPY'
static s8 s_CopyEngine = -1; // not asked yet
static bool CopyEngine(void) {
    if (s_CopyEngine < 0) {
        s_CopyEngine = COPY_REGS[3] == COPY_MAGIC;
    }
    return s_CopyEngine;
}
static void CopyWords(void* dst, const void* src, u32 len) {
    u32* d = dst;
    const u32* w = src;

    if (!len) {
        return;
    }
    if (CopyEngine()) {
        COPY_REGS[0] = (u32)dst;
        COPY_REGS[1] = (u32)src;
        COPY_REGS[2] = len;
        COPY_REGS[3] = 1;
        return;
    }
    for (len /= 4; len--;) {
        *d++ = *w++;
    }
}
static void ExchangeWords(void* a, void* b, u32 len) {
    u32 *x = a, *y = b, t;

    if (!len) {
        return;
    }
    if (CopyEngine()) {
        COPY_REGS[0] = (u32)a;
        COPY_REGS[1] = (u32)b;
        COPY_REGS[2] = len;
        COPY_REGS[3] = 2;
        return;
    }
    for (len /= 4; len--; x++, y++) {
        t = *x;
        *x = *y;
        *y = t;
    }
}

// Exchanges the game's copy with the partner's (region 0 first: the slots).
static void Swap(void) {
    u32* body = BODY_BUF;
    s32 i;

    if (B->code || B->aluHere) {
        ExchangeWords((u32*)HDR_ADDR, B->hdr, B->hdrWords * 4);
        ExchangeWords((u32*)g_api.o.spriteBanks + 16, B->banks, BANKS * 4);
    }
    // the 64 player slots: only those in use on either side (most are empty), and always the
    // player's (0). Its afterimages' (1-3: no id, but set up by AluInit and RicInit, slot 1
    // holding their primitives) too when it's another character than player 1: shared, Alucard's
    // afterimage code (8 primitives) walked Richter's or Maria's chain (6) to its end and wrote
    // through NULL, into the BIOS. Of the same character, they share them, as they always did:
    // never swapped, whatever their id (slot 1's is the afterimages' counter, alu_anim.c: when it
    // wrapped to 0 in the body's frame, player 1's slot stayed in the copy).
    for (i = 0; i < 64; i++, body += 0xBC / 4) {
        u32* ram = (u32*)&g_Entities[i];
        if (i && i <= E_AFTERIMAGE_3) {
            if (!B->otherChar) { // slot 1's id is a counter: 0 is no sign of an empty slot
                continue;
            }
        } else if (i && !((Entity*)ram)->entityId && !((Entity*)body)->entityId) {
            continue;
        }
        ExchangeWords(ram, body, 0xBC);
    }
    for (i = 1; i < LEN(s_Regions); i++) {
        ExchangeWords((u32*)s_Regions[i].addr, body, s_Regions[i].len);
        body += s_Regions[i].len / 4;
    }
}

static void SwapIn(void);
static bool PartnerLive(void);
static void SwapOut(void);

// A partner build's 'FAR1' trailer (characters/richter-ps1/ric_partner.ld, characters/maria-dx/maria_partner.ld): where the
// BSS starts, so it's kept before the first Make zeroes it, and where each body's own statics are
// (M17: Statics). Maria's has an eighth word, her init.
typedef struct {
    u32 magic, nearSize, farSize, bssSize, farAddr;
    u32 statics;   // each body's own data, from here to farAddr...
    u32 sharedBss; // ...and BSS, from its start to here (the rest, her palettes' copy, is shared)
    void (*init)(u16); // Maria's partner init (coop_maria.c); not in Richter's
} FarTrailer;
#define TRAILER_WORDS 7 // without an init
static bool Trailer(u32 base, u32 size, u32 words, FarTrailer* out) {
    const FarTrailer* t;

    if (size < words * 4 || size > PARTNER_SAT_SIZE) {
        return false;
    }
    t = (const FarTrailer*)(base + ((size - words * 4) & ~3));
    if (t->magic != 0x31524146 || t->farAddr != base + t->nearSize) {
        return false;
    }
    *out = *t;
    if (words <= TRAILER_WORDS) {
        out->init = NULL;
    }
    return true;
}

// The partner's Richter, as CoopBoot read it.
static const FarTrailer* PartnerRic(void) {
    static FarTrailer s_Trailer;

    if (!s_Trailer.magic && !Trailer(PARTNER_RIC_ADDR, g_CoopRicPartnerFile.size, TRAILER_WORDS, &s_Trailer)) {
        return NULL;
    }
    return &s_Trailer;
}

// The partner's Maria, from her blob (the launcher's, in every game where someone plays her: its
// last part), put where it runs once.
// Each Maria's partner build has a place of its own (module/coop_api.h): code copied over another's
// may go unnoticed by the recompiler. So each is copied there once, and kept (M17: partners on
// two Marias run both). Saturn Maria's has Richter's trailer: her init is her table's.
static const FarTrailer* PartnerMar(u32 character) {
    static FarTrailer s_Trailers[3]; // Co-op Maria's, Ultimate Maria's, Saturn Maria's
    const CharBlob* b;
    bool sat = character == CHAR_SAT_MARIA;
    FarTrailer* tr = &s_Trailers[sat ? 2 : character == CHAR_ULT_MARIA];
    u32 addr = sat ? PARTNER_SAT_ADDR : character == CHAR_ULT_MARIA ? PARTNER_ULT_ADDR : PARTNER_MAR_ADDR;
    const u32* src;
    u32* dst;
    u32 n;

    if (tr->magic) {
        return tr;
    }
    b = CharacterBlob(character);
    if (!b || !b->partnerSize ||
        b->partnerSize > (sat ? PARTNER_SAT_SIZE : character == CHAR_ULT_MARIA ? PARTNER_ULT_SIZE : PARTNER_PLAYER_SIZE)) {
        return NULL;
    }
    src = (const u32*)((const u8*)(b + 1) + ((b->ovlSize + 3) & ~3) + ((b->vhSize + 3) & ~3) +
                       ((b->vbSize + 3) & ~3));
    dst = (u32*)addr;
    for (n = (b->partnerSize + 3) / 4; n--;) {
        *dst++ = *src++;
    }
    FlushCache(); // new code (D17)
    if (!Trailer(addr, b->partnerSize, sat ? TRAILER_WORDS : TRAILER_WORDS + 1, tr) || (!sat && !tr->init)) {
        tr->magic = 0;
        return NULL;
    }
    return tr;
}

// Ultimate Richter as the partner runs our Richter's partner build (his code is retail Richter's,
// which can't run anywhere but 0x8013C000) with his coat's sprite table: his blob's, rebased to
// where the blob is. Its two moved frames (the coat's x/y fixes) are left as Richter's.
#define RIC_SHEET_WORDS (0x314 / 4) // richter_sprites (0x8013C020), in both files
static void UltRichterSheet(void) {
    const CharBlob* b = CharacterBlob(CHAR_ULT_RICHTER);
    const u32* file;
    u32 k;

    if (!b) {
        return;
    }
    file = (const u32*)(b + 1);
    for (k = 8; k < 8 + RIC_SHEET_WORDS; k++) {
        B->hdr[k] = file[k] - HDR_ADDR + (u32)file;
    }
}

static const FarTrailer* PartnerCode(u32 character) {
    // Saturn Maria isn't CHAR_IS_MARIA (her file is Richter's layout), but her partner build is a blob's
    return character == CHAR_RICHTER || character == CHAR_ULT_RICHTER ? PartnerRic()
           : CHAR_IS_MARIA(character) || character == CHAR_SAT_MARIA ? PartnerMar(character)
                                                                      : NULL;
}

// M17: partners on one character run one build (PartnerCode: one per character), so each body
// keeps that build's statics of its own: its data from the trailer's statics to its code, its BSS
// to the trailer's sharedBss (her palettes' copy after it is shared: at worst one's flash shows on
// the other), and Saturn Maria's live sprite table (her code rewrites it as it unpacks her
// images). The build holds the statics of the body that ran it last (s_Holder); another body's
// frame exchanges its own (kept in a buffer: s_BufOf) with those. Two of a kind: two exchanges a
// frame. Three bodies on one build keep two apart, so two buffers are enough.
#define STATICS_MAX 0x5000 // bytes; each partner build's linker script checks it fits
#define BUFFERS (COOP_PARTNERS - 1)
#define BUILDS 4 // Richter's (Ultimate Richter's too), Co-op Maria's, Ultimate Maria's, Saturn Maria's
static u32 s_Statics[BUFFERS][STATICS_MAX / 4];
static s8 s_Holder[BUILDS] = {-1, -1, -1, -1};     // the body whose statics the build holds (-1: none)
static s8 s_BufOf[COOP_PARTNERS] = {-1, -1, -1}; // the buffer holding body k's (-1: none)
enum { STATICS_SAVE, STATICS_LOAD, STATICS_EXCHANGE };

static s32 BuildOf(u32 chr) {
    return chr == CHAR_RICHTER || chr == CHAR_ULT_RICHTER ? 0
           : chr == CHAR_ULT_MARIA                        ? 2
           : chr == CHAR_SAT_MARIA                        ? 3
           : CHAR_IS_MARIA(chr)                           ? 1
                                                          : -1;
}

// Build b's statics (B's character runs it) and a buffer: to the buffer, from it, or exchanged.
static void StaticsBuf(s32 b, u32* buf, s32 op) {
    static const u32 bases[BUILDS] = {PARTNER_RIC_ADDR, PARTNER_MAR_ADDR, PARTNER_ULT_ADDR, PARTNER_SAT_ADDR};
    const FarTrailer* t = PartnerCode(B->chr);
    u32 spans[3][2], *end = buf + STATICS_MAX / 4, n, k;

    if (!t) {
        return;
    }
    spans[0][0] = bases[b]; // Saturn Maria's live sprite table (B->liveHdr)
    spans[0][1] = b == 3 ? HDR_SIZE_SAT : 0;
    spans[1][0] = t->statics;
    spans[1][1] = t->farAddr - t->statics;
    spans[2][0] = t->farAddr + t->farSize;
    spans[2][1] = t->sharedBss - spans[2][0];
    for (k = 0; k < 3; k++) {
        n = spans[k][1] / 4;
        n = n < (u32)(end - buf) ? n : (u32)(end - buf);
        if (op == STATICS_SAVE) {
            CopyWords(buf, (u32*)spans[k][0], n * 4);
        } else if (op == STATICS_LOAD) {
            CopyWords((u32*)spans[k][0], buf, n * 4);
        } else {
            ExchangeWords((u32*)spans[k][0], buf, n * 4);
        }
        buf += n;
    }
}
static void Statics(s32 b, s32 i, s32 op) { StaticsBuf(b, s_Statics[i], op); }

static s32 FreeBuffer(void) {
    s32 i, k;

    for (i = 0; i < BUFFERS; i++) {
        for (k = 0; k < COOP_PARTNERS && s_BufOf[k] != i; k++) {
        }
        if (k == COOP_PARTNERS) {
            return i;
        }
    }
    return -1;
}

// Before the body's code runs: its statics in its build, and the last holder's kept.
static void StaticsIn(void) {
    s32 b = BuildOf(B->chr), j, i;

    if (b < 0 || (j = s_Holder[b]) == s_K) {
        return;
    }
    i = s_BufOf[s_K];
    if (j >= 0 && i >= 0) {
        Statics(b, i, STATICS_EXCHANGE);
        s_BufOf[j] = i;
    } else if (j >= 0 && (i = FreeBuffer()) >= 0) { // ours were never kept apart: we take its
        Statics(b, i, STATICS_SAVE);
        s_BufOf[j] = i;
    } else if (i >= 0) { // nobody's in the build (its holder went to another character)
        Statics(b, i, STATICS_LOAD);
    }
    s_BufOf[s_K] = -1;
    s_Holder[b] = s_K;
}

// A body made: it starts from its build as it is (as a body made again always has), and whoever
// held it keeps theirs. What it kept of another build is nobody's now.
static void StaticsMade(void) {
    s32 b = BuildOf(B->chr), j, i, k;

    for (k = 0; k < BUILDS; k++) {
        if (s_Holder[k] == s_K) {
            s_Holder[k] = -1;
        }
    }
    s_BufOf[s_K] = -1;
    if (b < 0) {
        return;
    }
    j = s_Holder[b];
    if (j >= 0 && (i = FreeBuffer()) >= 0) {
        Statics(b, i, STATICS_SAVE);
        s_BufOf[j] = i;
    }
    s_Holder[b] = s_K;
}

// A character's graphics file in the body's VRAM bank, where the game puts its own in the first:
// 32 strips of 32x128 for x 0x200-0x3FF, y 0x100-0x1FF (src/dra/cd.c), then palettes 0x100-0x1FF
// (x 0-0xFF, y 0xF0-0xFF).
static void LoadGraphics(const u8* file, const u8* palettes) {
    RECT r;
    s32 i;

    for (i = 0; i < 0x20; i++) {
        r.x = D_800AC958[i];
        r.y = (i & 2 ? 0x180 : 0x100) | VRAM_BANK_OF(B->bank);
        r.w = 0x20;
        r.h = 0x80;
        if (i == 0x1A) { // as the game does: its first row is a palette (0x380, 0x180)
            r.y = 0x181 | VRAM_BANK_OF(B->bank);
            r.h = 0x7F;
        }
        LoadImage(&r, (u_long*)(file + i * 0x2000));
        DrawSync(0);
    }
    r.x = 0;
    r.y = 0xF0 | VRAM_BANK_OF(B->bank);
    r.w = 0x100;
    r.h = 0x10;
    LoadImage(&r, (u_long*)palettes);
    DrawSync(0);
}

// Alucard's ARC_F.BIN as DRA reads it, from CoopBoot's copy (linked at 0x8013C000): its header
// words point at the sprite table (0x8013C020, swapped in as it is), except the bat's table, and
// the 218 sprite and 6 bat sprite pointers are rebased onto the copy.

static void AluHeader(void) {
    const u32* arc = (const u32*)ARC_F_ADDR;
    u32 delta = ARC_F_ADDR - HDR_ADDR, k;

    B->hdrWords = HDR_SIZE / 4;
    B->liveHdr = NULL;
    for (k = 0; k < HDR_SIZE / 4; k++) {
        B->hdr[k] = arc[k];
    }
    for (k = 8; k < 8 + ALU_SHEETS; k++) {
        if (B->hdr[k]) {
            B->hdr[k] += delta;
        }
    }
    for (k = 0; k < ALU_BATS; k++) {
        B->aluBats[k] = ((const u32*)(arc[1] + delta))[k] + delta;
    }
    B->hdr[1] = (u32)B->aluBats;
}

// DRA's own palette load for Alucard (op 0x16: palettes 0x100-0x10D, src/dra/4A538.c), into the
// body's bank, as his init would have them in the first.
extern u_long* D_800A3BB8[]; // DRA
static void AluPalettes(void) {
    const u_long* op = D_800A3BB8[0x16];
    const u16* colors = (const u16*)op[3]; // its colors, where op[3] points
    u32 first = op[1] / 16, k;
    RECT r;

    if (op[0] != 1) {
        return;
    }
    for (k = 0; k < op[2] / 16; k++) {
        u16 clut = g_ClutIds[first + k];
        r.x = (clut & 0x3F) * 16;
        r.y = ((clut >> 6) & 0x1FF) | VRAM_BANK_OF(B->bank);
        r.w = 16;
        r.h = 1;
        LoadImage(&r, (u_long*)(colors + k * 16));
        DrawSync(0);
    }
}

// The partner starts as a copy of player 1, a little to the right.
#define DRAW_OFS (64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4)) // g_PlayerDraw in the copy

#define PLAYER_HIT_MARGIN 1000
u32 g_CoopBodyHits; // hits given to the body (tests read it: coop.map)
u32 g_CoopBodyOff; // tests: no partner body (it's drawn by nothing then)
u32 g_CoopBodyTeleports; // bodies made with the partner's teleport-in (tests read it: coop.map)
u32 g_CoopBodiesMade; // M17: bit k, partner k's body is made (tests read it: coop.map)

static void Make(void) {
    u32* body = BODY_BUF;
    PlayerDraw* draw;
    s32 i;
    u32 k;
    // just revived: its init plays its character's teleport-in (arrive.c's TeleportIn)
    s32 how = PartnerLive() && (Presence()->flipX & FLIP_TELEPORT_IN) ? 6 : 0;
    s32 saved;

    g_CoopBodyTeleports += how != 0;

    for (i = 0; i < LEN(s_Regions); i++) {
        u32* ram = (u32*)s_Regions[i].addr;
        for (k = 0; k < s_Regions[i].len / 4; k++) {
            *body++ = ram[k];
        }
    }
    ((Entity*)BODY_BUF)->posX.i.hi += 32;
    B->chr = PartnerLive() ? Presence()->character : CHAR_ALUCARD;
    B->code = B->chr != CHAR_ALUCARD;
    StaticsMade();
    B->aluHere = !B->code && CharacterLoaded() != CHAR_ALUCARD;
    // A partner build's own uploads always go to the body's bank (coop_ric.h): it draws from there.
    B->banked = B->code || B->chr != CharacterLoaded();
    B->otherChar = B->chr != CharacterLoaded();
    B->reloaded = false;
    B->partnerHp = -1; // its first status here isn't a hit
    B->scrollX = g_Tilemap.scrollX.i.hi; // for SwapIn: no camera move to apply to the copy
    B->scrollY = g_Tilemap.scrollY.i.hi;
    if (B->banked && B->bankLoaded != B->chr) { // before the init: Maria's uploads her palettes
        if (B->chr == CHAR_ALUCARD) {
            LoadGraphics((const u8*)FGAME_GFX_ADDR, (const u8*)FGAME_PAL_ADDR);
            AluPalettes();
        } else {
            LoadGraphics((const u8*)FGAME2_ADDR, (const u8*)FGAME2_ADDR + 0x40000); // Richter's; Maria's runs on it too
            if (B->chr == CHAR_ULT_RICHTER && CharacterBlob(CHAR_ULT_RICHTER)) { // his coat's colours and arm
                CharacterRicCoat((const u8*)(CharacterBlob(CHAR_ULT_RICHTER) + 1), B->bank);
            }
        }
        B->bankLoaded = B->chr;
        FamiliarReload(s_K); // the strips held the partner's familiar too
    }
    if (!B->code) { // DRA's Alucard, from his own init, with nothing of player 1's (slots 1-63
                   // hold player 1's afterimages, familiar, weapons: their primitives are player 1's)
        Entity* pl = (Entity*)BODY_BUF;
        s16 x = pl->posX.i.hi, y = pl->posY.i.hi;

        if (B->aluHere) {
            AluHeader();
            for (k = 0; k < BANKS; k++) {
                B->banks[k] = ((u32*)g_api.o.spriteBanks)[16 + k];
            }
        }
        for (k = 0xBC / 4; k < 64 * 0xBC / 4; k++) {
            BODY_BUF[k] = 0;
        }
        SwapIn();
        saved = D_80097C98; // player 1's (it may be set during a load)
        D_80097C98 = how;
        AluInit();
        D_80097C98 = saved;
        SwapOut();
        pl->posX.i.hi = x; // where the copy was (the partner's spot, below, when it's live)
        pl->posY.i.hi = y;
    }
    if (B->code) { // their own code, started by its own init, with nothing of player 1's
        const FarTrailer* t = PartnerCode(B->chr);
        const u32* hdr = (const u32*)(t->farAddr - t->nearSize);
        u32* bss = (u32*)(t->farAddr + t->farSize);
        u32* banks = (u32*)g_api.o.spriteBanks + 16;

        for (k = 0; k < t->bssSize / 4; k++) { // fresh statics (the trailer is in the first words)
            bss[k] = 0;
        }
        B->hdrWords = (B->chr == CHAR_SAT_MARIA ? HDR_SIZE_SAT : HDR_SIZE) / 4;
        B->liveHdr = B->chr == CHAR_SAT_MARIA ? hdr : NULL;
        for (k = 0; k < B->hdrWords; k++) {
            B->hdr[k] = hdr[k];
        }
        if (B->chr == CHAR_ULT_RICHTER) {
            UltRichterSheet();
        }
        for (k = 0; k < BANKS; k++) {
            B->banks[k] = banks[k];
        }
        for (k = 0xBC / 4; k < 64 * 0xBC / 4; k++) { // slots 1-63: player 1's (their primitives too)
            BODY_BUF[k] = 0;
        }
        SwapIn();
        saved = D_80097C98;
        D_80097C98 = how;
        if (t->init) {
            t->init(0);
        } else {
            ((PlayerOvl*)HDR_ADDR)->D_8013C004(0);
        }
        D_80097C98 = saved;
        SwapOut();
    }
    // Its sprites go to its VRAM bank, where player 1's would be (RenderEntities loads each
    // player-sprite frame into its g_PlayerDraw slot as it draws, and clears its edges): y bits 9-10
    // for the uploads and fills, texpage bits 14-15 for the drawing (our SwanStation build:
    // patches/swanstation.patch).
    draw = (PlayerDraw*)((u8*)BODY_BUF + DRAW_OFS);
    for (i = 0; i < 16; i++, draw++) {
        draw->rect0.y |= VRAM_BANK_OF(B->bank);
        draw->rect1.y |= VRAM_BANK_OF(B->bank);
        draw->rect2.y |= VRAM_BANK_OF(B->bank);
        draw->tpage |= TPAGE_BANK_OF(B->bank);
    }
    B->made = true;
    s_Roll[s_K].on = false;
}

// Entity positions are on screen (relative to the camera), and the camera moved while the copy
// was out of RAM: its slots move with it, as the game moves its own entities.
// The body's Alucard code checks for a level up, on this player's XP and the partner's stats: that
// level's gains were swapped out with the stats, and Richter leveled with his growth rule off.
static s32 s_KeptExp;

// The HP numbers the partner's hits make (DRA's CreateHPNumMove, our CharacterDamageNumber) fly to
// this player's HP meter, as if this player was hit (#299): the ones made during its turn go.
#define NUM_FIRST 0x38
#define NUM_END 0x40
#define DRA_ENT_HPNUM 19
#define COOP_ENT_HPNUM 0xCF
static u8 s_NumsBefore;

static u8 HpNumbers(void) {
    u8 mask = 0;
    s32 i;

    for (i = NUM_FIRST; i < NUM_END; i++) {
        if (g_Entities[i].entityId == DRA_ENT_HPNUM || g_Entities[i].entityId == COOP_ENT_HPNUM) {
            mask |= 1 << (i - NUM_FIRST);
        }
    }
    return mask;
}

static void SwapIn(void) {
    s16 dx = B->scrollX - g_Tilemap.scrollX.i.hi, dy = B->scrollY - g_Tilemap.scrollY.i.hi;
    s32 i;
    u32 k;

    if (B->code) {
        StaticsIn();
        g_CoopPartnerVram = VRAM_BANK_OF(B->bank); // its build's uploads (coop_partner.c)
    }
    if (B->code && B->liveHdr) { // Saturn Maria's: her table as her code last left it
        for (k = 0; k < B->hdrWords; k++) {
            B->hdr[k] = B->liveHdr[k];
        }
    }
    s_NumsBefore = HpNumbers();
    Swap();
    s_KeptExp = g_Status.exp;
    g_Status.exp = 0;
    s_SavedChar = g_CoopCharacter;
    s_SavedRandom = g_randomNext; // the partner's randomness doesn't change our game's
    s_SfxPos = g_sfxRingBufferWritePos;
    s_CmdPos = g_SoundCommandRingBufferWritePos;
    BodyWeaponsIn();
    WeaponsOff();
    RandOff();
    g_CoopCharacter = B->code ? PLAYER_RICHTER : PLAYER_ALUCARD; // Maria's runs as Richter's too
    if (!B->code) { // his palette operations would work on player 1's palettes: none kept
        for (i = 0; i < LEN(D_8006C3C4); i++) {
            B->palOps[i] = D_8006C3C4[i];
        }
    }
    if (B->code) {
        GfxBefore();
    }
    for (i = 0; i < 64; i++) {
        if (i == 0 || (g_Entities[i].entityId && (i > E_AFTERIMAGE_3 || B->otherChar))) { // not player 1's (Swap)
            g_Entities[i].posX.i.hi += dx;
            g_Entities[i].posY.i.hi += dy;
        }
    }
}

// The partner's own status (stats, level, equipment: link.h's CoopStatus, sent by its host) in
// the copy, so it fights and casts as itself. Without it (an older partner), it keeps player 1's.
static void PutStatus(void) {
    const CoopStatus* st = StatusIn();
    u8* body = (u8*)BODY_BUF + 64 * 0xBC;
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

// Since the body never runs the weapons' code (WeaponsOff), its swings always come from the link.
// A weapon the body runs itself is drawn with it (#343); the others, from the link (weapons.c).
bool PartnerWeaponDiffers(s32 hand) { return !B->wpnRun[hand & 1]; }

// Where the partner's own sprites and hitboxes (sent from its game: weapons.c, pvp.c) are drawn: moved
// by where the body is drawn against where the partner stood when they were made. Rolling, that's
// the spot its host gives for the sprites' own frame (the presence is from frames before them).
void PartnerBodyOffset(s16* dx, s16* dy) {
    const Entity* body = (const Entity*)BODY_BUF;
    volatile CoopRollIn* in = ROLL_IN(s_K);
    s16 x = Presence()->x, y = Presence()->y;

    if (s_Roll[s_K].on && in->magic == ROLL_MAGIC && (u32)(in->newest - in->spriteFrame) < ROLL_PADS) {
        x = in->spriteX;
        y = in->spriteY;
    }
    *dx = body->posX.i.hi + B->scrollX - x + (s_Roll[s_K].on ? s_Roll[s_K].drawX : 0);
    *dy = body->posY.i.hi + B->scrollY - y + (s_Roll[s_K].on ? s_Roll[s_K].drawY : 0);
}

static void SwapOut(void) {
    g_Status.exp += s_KeptExp;
    B->scrollX = g_Tilemap.scrollX.i.hi;
    B->scrollY = g_Tilemap.scrollY.i.hi;
    if (B->code) {
        GfxAfter();
    }
    PartnerSounds(); // the body is still in RAM: its spot pans them
    RandOn();
    WeaponsOn();
    BodyWeaponsOut();
    g_CoopCharacter = s_SavedChar;
    g_randomNext = s_SavedRandom;
    if (!B->code) {
        s32 i;
        for (i = 0; i < LEN(D_8006C3C4); i++) {
            D_8006C3C4[i] = B->palOps[i];
        }
    }
    Swap();
    {
        u8 made = HpNumbers() & ~s_NumsBefore;
        s32 i;

        for (i = NUM_FIRST; made; i++, made >>= 1) {
            if (made & 1) {
                DestroyEntity(&g_Entities[i]);
            }
        }
    }
}

// Its body outlasts a stall of the link (it blinked in and out with each one: playtest 0.14), standing
// still once its buttons stop coming.
#define BODY_STALE_FRAMES 300
static bool PartnerLive(void) { return Age() <= BODY_STALE_FRAMES; }

// The partner is in this room, in play, as a character we can run: Alucard (DRA's code), Richter or
// Maria (their partner builds), in any game.
static bool PartnerHere(void) {
    const CoopPresence* p = Presence();
    return p->stage == g_CoopStage && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top &&
           (p->flags & PRESENCE_IN_PLAY) && g_PlayableCharacter == 0 &&
           (p->character == CHAR_ALUCARD || PartnerCode(p->character));
}

// The body's primitives (its entities' chains), for its own drawing pass. Up to PRIMS of them.

// Slot i (the body's slots swapped in) holds primitives of the body's own: an entity's, or its
// afterimages' (slot 1: no id) when they're its own (another character: Swap). Of player 1's
// character, slots 1-3 aren't swapped: they're player 1's own, never the body's to free.
static bool OwnPrims(s32 i) {
    if (!(g_Entities[i].flags & FLAG_HAS_PRIMS)) {
        return false;
    }
    if (i && i <= E_AFTERIMAGE_3) { // no id (slot 1's is the afterimages' counter)
        return B->otherChar;
    }
    return i == 0 || g_Entities[i].entityId;
}

static void FindPrims(void) {
    Primitive* prim;
    s32 i;

    B->primCount = 0;
    for (i = 0; i < 64; i++) {
        if (OwnPrims(i)) {
            for (prim = &g_PrimBuf[g_Entities[i].primIndex]; prim && B->primCount < PRIMS; prim = prim->next) {
                B->prims[B->primCount++] = prim - g_PrimBuf;
            }
        }
    }
}

// A primitive of the body's that covers the screen (its teleport-in's white flash): that's this
// game's player's screen, not the body's to flash. Hidden from every pass, given back after.

// As big as most of the screen (the teleport's are two 0xC0 x 0xF0 tiles and a quad: EntityTeleport).
static bool CoversScreen(const Primitive* p) {
    if (p->type == PRIM_TILE) {
        return p->u0 >= 0xC0 && p->v0 >= 0xE0; // w, h in u0, v0
    }
    return p->x3 - p->x0 >= 0xC0 && p->y3 - p->y0 >= 0xE0;
}

static void HideFlashes(void) {
    Primitive* p;
    s32 i;

    for (i = 0; i < B->primCount && B->flashCount < FLASHES; i++) {
        p = &g_PrimBuf[B->prims[i]];
        if (!(p->drawMode & DRAW_HIDE) && CoversScreen(p)) {
            p->drawMode |= DRAW_HIDE;
            B->flash[B->flashCount++] = B->prims[i];
        }
    }
}

// Back as the body left them, before its frame (hidden from the game's pass after its own).
static void UndoShift(void);
static void ShowPrims(void) {
    s32 i;

    UndoShift();
    for (i = 0; i < B->primCount; i++) {
        if (B->primHidden[i]) {
            g_PrimBuf[B->prims[i]].drawMode &= ~DRAW_HIDE;
        }
    }
    for (i = 0; i < B->flashCount; i++) {
        g_PrimBuf[B->flash[i]].drawMode &= ~DRAW_HIDE;
    }
    B->primCount = 0;
    B->flashCount = 0;
}

// The body leaves: its primitives go back to the game, unless a stage load freed them all.
static void Drop(void) {
    s32 i;

    if (B->made && !B->reloaded) {
        ShowPrims();
        SwapIn();
        for (i = 0; i < 64; i++) {
            if (OwnPrims(i)) {
                g_api.FreePrimitives(g_Entities[i].primIndex);
                g_Entities[i].flags &= ~FLAG_HAS_PRIMS;
            }
        }
        SwapOut();
    }
    B->made = false;
    B->primCount = 0;
    s_Roll[s_K].on = false;
}

// The harness's spike test only (OPT_PARTNER_SIM, no partner): a copy of player 1 on g_CoopSpikePad.
static bool Spike(void) { return !s_K && (g_CoopOptions & OPT_PARTNER_SIM) && !PartnerLive(); }

bool PartnerSimulated(void) {
    return B->made && (Spike() || (PartnerLive() && PartnerHere()));
}

static void Draw(void);

// Alucard's afterimages, with their primitives gone, write through whatever replaced them: every
// frame func_801093C4 takes a DR_ENV pointer from another entity's primitive. That walked up low
// memory into the exception vector and hung the game for good (playtest 2026-11-01). Set up again
// as AluInit does. Tests read the count: coop.map.
#define AFTERIMAGE_PRIMS 8
u32 g_CoopAfterimagesRepaired;

static void KeepAfterimages(void) {
    Entity* e = &g_Entities[E_AFTERIMAGE_1];
    Primitive* prim;
    s32 i, index;

    if (CharacterLoaded() != CHAR_ALUCARD || (e->flags & FLAG_HAS_PRIMS)) {
        return;
    }
    index = g_api.AllocPrimitives(PRIM_TILE, AFTERIMAGE_PRIMS);
    if (index < 0) {
        g_Player.unk6A = 0xFFFF; // no pool either: func_801093C4 does nothing in this state
        return;
    }
    e->primIndex = index;
    e->flags |= FLAG_HAS_PRIMS;
    for (prim = &g_PrimBuf[index], i = 0; i < 6; i++, prim = prim->next) {
        prim->drawMode = DRAW_UNK_100 | DRAW_HIDE | DRAW_UNK02;
    }
    g_Player.unk6A = 0;
    g_CoopAfterimagesRepaired++;
}

// An Alucard partner's form (bat, wolf) as its presence draws it. A body made while the partner is
// already a bat (through a door, or the room's first sight of them) starts on foot, and nothing
// pressed the button that would change it: it fell, was pulled back to the bat, and drew as Alucard
// mid-jump (zhika, 1.0.0). Apart this long, the body gets that form's button, as if the partner had
// pressed it, and its own code changes it (DRA: R1 the bat, R2 the wolf, through the button map).
#define FORM_FRAMES 20
#define ANIMSET_BAT 13
#define ANIMSET_WOLF 15
#define BUTTON_WOLF 4 // g_Settings.buttonMask's index of PAD_R2 (D_800ACE00)
#define BUTTON_BAT 6  // of PAD_R1
u32 g_CoopBodyForms; // form buttons given to the body (tests read it: coop.map)

static u16 FormButton(const CoopPresence* p) {
    s16 want = p->animSet, is = PLAYER.animSet;
    s32 button;

    if (B->code || want == is) {
        B->formApart = 0;
        return 0;
    }
    button = want == ANIMSET_BAT || is == ANIMSET_BAT     ? BUTTON_BAT
             : want == ANIMSET_WOLF || is == ANIMSET_WOLF ? BUTTON_WOLF
                                                          : -1;
    if (button < 0 || ++B->formApart < FORM_FRAMES) {
        return 0;
    }
    B->formApart = 0; // again after as long, if its code didn't take it
    g_CoopBodyForms++;
    return g_Settings.buttonMask[button];
}

static void BodyFrame(void);

// Each partner's frame: its update and its drawing, in one swap. After player 1's RenderEntities.
void PartnerFrame(void) {
    s32 k;

    if (!s_BodiesSet) {
        SetBodies();
    }
    if (ArriveCardSaving()) {
        return; // the game is frozen while its card is written (the card and pads share the port)
    }
    // A load (a stage, a save, a teleport's arrival) frees every primitive and replaces the stage's
    // sprite-bank table: the body goes with it, and is made again in play. The load ends in
    // Play_Default with Engine_Init, which frees every primitive too: until that's run, no body (one
    // made before it lost its primitives, walked the chains that replaced them to their end and
    // wrote through NULL: the BIOS's pad driver died).
    if (g_GameState != Game_Play || g_GameStep != Play_Default) {
        s_AfterLoad = true;
    } else if (s_AfterLoad && g_GameEngineStep != Engine_Init) {
        s_AfterLoad = false;
    }
    if (s_AfterLoad) {
        g_CoopBodiesMade = 0;
        for (k = 0; k < COOP_PARTNERS; k++) {
            s_Bodies[k].reloaded = true;
            s_Bodies[k].made = false;
            s_Bodies[k].primCount = 0;
            s_Bodies[k].flashCount = 0;
            s_Roll[k].on = false;
            s_Roll[k].shiftX = s_Roll[k].shiftY = 0; // its primitives went with the load
        }
        return;
    }
    KeepAfterimages();
    g_CoopBodiesMade = 0;
    for (k = 0; k < COOP_PARTNERS; k++) {
        s_K = k;
        B = &s_Bodies[k];
        BodyFrame();
        g_CoopBodiesMade |= B->made << k;
    }
    s_K = 0;
    B = s_Bodies;
}

// HP the partner lost in its own game since the last frame (its status says): its own hit reaction
// here, its own code's knockback and voice (cosmetic: the body's status is the partner's).
static s32 HitIn(void) {
    s32 hp, lost = 0;

    if (!PartnerLive() || StatusIn()->magic != STATUS_MAGIC) {
        return 0;
    }
    hp = ((const s32*)(StatusIn())->a)[1]; // g_Status.hp
    if (B->partnerHp > hp && hp > 0) {
        lost = B->partnerHp - hp;
    }
    B->partnerHp = hp;
    return lost;
}

// Pulled to the partner's real spot when it drifts (swapped in).
static void Pull(const CoopPresence* p) {
    s16 x = p->x - g_Tilemap.scrollX.i.hi, y = p->y - g_Tilemap.scrollY.i.hi;
    s32 dx = x - PLAYER.posX.i.hi, dy = y - PLAYER.posY.i.hi;
    bool off = Ease(dx) || Ease(dy);

    B->driftFrames = off ? B->driftFrames + 1 : 0;
    if (dx > SNAP_PX || -dx > SNAP_PX || dy > SNAP_PX || -dy > SNAP_PX || B->driftFrames > DRIFT_FRAMES) {
        // A door, a teleport, or a drift the easing can't undo (a body on a floor below its
        // real spot falls back each frame): there at once.
        PLAYER.posX.i.hi = x;
        PLAYER.posY.i.hi = y;
        PLAYER.velocityX = PLAYER.velocityY = 0;
        B->driftFrames = 0;
    } else {
        // Drifting (its game's hit knocked it back, and not here): eased back, an eighth of the
        // way a frame. Snapped at 48 px, Richter running "jumped all over" (#291).
        PLAYER.posX.i.hi += Ease(dx);
        PLAYER.posY.i.hi += Ease(dy);
    }
}

// One frame of the body's own code on these buttons (swapped in). again: a frame it ran before,
// run again from a rollback (its sounds were heard then: SwapOut drops them).
static void Run(const CoopPresence* p, u16 pad, s32 hit, bool again) {
    Pad pad0;
    u32 options;
    Entity* cur;
    s32 i;

    if (hit) {
        // Its own code's sums can differ from its game's, and a body that died here stayed dead
        // and unseen while the partner played on (playtest 0.14): it can't die of this.
        g_Status.hp = g_Status.hpMax + PLAYER_HIT_MARGIN + hit;
        PLAYER.hitParams = DAMAGEKIND_1;
        PLAYER.hitPoints = hit + g_Status.defenseEquip;
        g_CoopBodyHits += !again && !s_SfxLog; // rolling: counted where it's new (RollFrame)
    }
    if (PartnerLive() && (p->flipX & FLIP_CARRIED)) { // hanging under a bat: where its own game holds it
        PLAYER.posX.val = (p->x - g_Tilemap.scrollX.i.hi) << 16;
        PLAYER.posY.val = (p->y - g_Tilemap.scrollY.i.hi) << 16;
        PLAYER.velocityX = PLAYER.velocityY = 0;
        pad = 0; // carry.c: its buttons are off while it hangs on
    } else if (PartnerLive()) {
        pad |= FormButton(p);
    }
    // Facing the partner's way (#274): a body made facing the other way kept it until the partner
    // pressed left or right, and threw its sub-weapons backwards. Not while it turns itself.
    if (PartnerLive() && !(pad & (PAD_LEFT | PAD_RIGHT)) && PLAYER.facingLeft != (p->flipX & 1)) {
        PLAYER.facingLeft = p->flipX & 1;
    }
    pad0 = g_pads[0];
    options = g_CoopOptions; // its one-button moves are on or off as the partner has them
    g_CoopOptions = (options & ~OPT_SHORTCUTS) | ((p->flipX & FLIP_SHORTCUTS) ? OPT_SHORTCUTS : 0);
    g_pads[0].pressed = pad;
    g_pads[0].tapped = pad & ~B->prevPad;
    g_pads[0].repeat = g_pads[0].tapped;
    B->prevPad = pad;
    cur = g_CurrentEntity;
    g_CurrentEntity = &PLAYER;
    if (B->code) { // as DRA runs Richter's (src/dra/5087C.c)
        ((PlayerOvl*)HDR_ADDR)->D_8013C000();
        ((PlayerOvl*)HDR_ADDR)->D_8013C008();
    } else {
        EntityAlucard();
        UpdatePlayerEntities();
    }
    for (i = 1; i < 64; i++) { // its weapons' and familiar's entities: not its to run (WeaponsOff)
        u16 id = g_Entities[i].entityId;
        if (id >= 0xD0 && !(id >= 0xE0 && B->wpnRun[(id - 0xE0) >> 4])) {
            DestroyEntity(&g_Entities[i]);
        }
    }
    g_CurrentEntity = cur;
    g_pads[0] = pad0;
    g_CoopOptions = options;
    B->bodyDied = (g_Player.status & PLAYER_STATUS_DEAD) && !(p->flags & PRESENCE_DEAD);
    s_Again = again;
}

// --- Rollback (#86, design/rollback.md). Online, the host writes the partner's buttons by frame as
// they come (link.h CoopRollIn), and the frame the partner is at now. The body runs up to that
// frame: on its buttons where they came, on a guess where they haven't yet (the last ones held).
// Before each frame it runs, its whole state is kept (RollSnap: the body, its statics, its
// primitives); when the buttons come and a guess was wrong, it goes back to the state before that
// frame and runs again from there, the frames it ran before without their sounds. So the partner
// is shown where they are now, not where they were half a round trip and the jitter buffer ago.
// The snapshots live in the 16 MB of our SwanStation build, and are taken by its copy engine.
#define ROLL_FRAMES 32 // snapshots kept, a power of two
#define ROLL_LEAD 12   // the most frames run on guesses (0.2 s)
#define ROLL_LINES 100 // running again stops once it has taken this many scanlines (of a frame's 263)
typedef struct {
    u32 frame; // the partner's frame this is the state before
    u16 pad;   // the buttons that frame ran on
    u8 guessed;
    u8 primCount;
    s32 hit; // HP its game lost, given to it before that frame
    SfxLog sfx; // the sounds that frame played (when it runs again, only what's new plays)
    Body b;
    u32 body[BODY_SIZE / 4];
    u32 statics[STATICS_MAX / 4];
    s16 primAt[PRIMS];
    Primitive prims[PRIMS];
    u32 weapons[2][0x3400 / 4]; // its own weapons' programs and palettes (#343: BODY_WEAPON)
} RollSnap;
#define ROLL_RING(k) ((RollSnap*)(ROLL_ADDR + 0x1000) + (k) * ROLL_FRAMES)
typedef char RollFits[ROLL_ADDR + 0x1000 + COOP_PARTNERS * ROLL_FRAMES * sizeof(RollSnap) <= 0x80F00000 ? 1 : -1];
u32 g_CoopRollFrames;   // tests (coop.map): frames run ahead
u32 g_CoopRollRewinds;  // rollbacks
u32 g_CoopRollAborts;   // rollbacks given up (a primitive it gave up was taken since)
u32 g_CoopRollBehind;   // frames the body was drawn short of the partner's (no time to run them all)
u32 g_CoopRollStartLine; // the scanline its turn started on, last frame (tests)
u32 g_CoopRollLinesMax;  // the most scanlines a turn took
s16 g_CoopRollDrawn[2];  // partner 0's body is drawn this far from where it is (tests: a correction sliding out)

static bool RollOn(const CoopPresence* p) {
    return PartnerLive() && ROLL_IN(s_K)->magic == ROLL_MAGIC && Age() <= PARTNER_STALE_FRAMES &&
           !(p->flipX & FLIP_CARRIED) && CopyEngine();
}

// The body's primitives, from its slots in the copy (swapped out): as OwnPrims says of RAM.
static s32 BodyPrims(s16* out) {
    const Entity* e = (const Entity*)BODY_BUF;
    Primitive* prim;
    s32 i, n = 0;

    for (i = 0; i < 64; i++, e++) {
        if (!(e->flags & FLAG_HAS_PRIMS) || (i && i <= E_AFTERIMAGE_3 ? !B->otherChar : i && !e->entityId)) {
            continue;
        }
        for (prim = &g_PrimBuf[e->primIndex]; prim && n < PRIMS; prim = prim->next) {
            out[n++] = prim - g_PrimBuf;
        }
    }
    return n;
}

// The body's state before frame f (swapped out), and what that frame runs on.
static void Keep(u32 f, u16 pad, u8 guessed, s32 hit) {
    RollSnap* r = &ROLL_RING(s_K)[f % ROLL_FRAMES];
    s32 i;

    r->frame = f;
    r->pad = pad;
    r->guessed = guessed;
    r->hit = hit;
    CopyWords(&r->b, B, sizeof(Body));
    CopyWords(r->body, BODY_BUF, BODY_SIZE / 4 * 4);
    if (B->code) {
        StaticsIn();
        StaticsBuf(BuildOf(B->chr), r->statics, STATICS_SAVE);
    }
    if (B->wpnSeq[0] || B->wpnSeq[1]) {
        CopyWords(r->weapons, BODY_WEAPON(s_K, 0), sizeof(r->weapons));
    }
    r->primCount = BodyPrims(r->primAt);
    for (i = 0; i < r->primCount; i++) {
        CopyWords(&r->prims[i], &g_PrimBuf[r->primAt[i]], sizeof(Primitive));
    }
}

// Back to the state before frame f. Its primitives as they were: those it took since go back to the
// game, and those it gave up since come back, unless something took them meanwhile (then it can't:
// false, nothing changed).
static bool Restore(u32 f) {
    RollSnap* r = &ROLL_RING(s_K)[f % ROLL_FRAMES];
    s16 now[PRIMS];
    s32 n, i, j, hp;
    bool reloaded, made, died, seen;
    s16 drift;
    u32 loaded;
    Primitive* prim;

    if (r->frame != f) {
        return false;
    }
    n = BodyPrims(now);
    for (i = 0; i < r->primCount; i++) {
        for (j = 0; j < n && now[j] != r->primAt[i]; j++) {
        }
        if (j == n && (g_PrimBuf[r->primAt[i]].type != PRIM_NONE || r->prims[i].type == PRIM_ENV)) {
            return false;
        }
    }
    for (j = 0; j < n; j++) {
        for (i = 0; i < r->primCount && r->primAt[i] != now[j]; i++) {
        }
        if (i == r->primCount) { // as FreePrimitives
            prim = &g_PrimBuf[now[j]];
            if (prim->type == PRIM_ENV) {
                **(DR_ENV***)&prim->r1 = NULL;
            }
            prim->type = PRIM_NONE;
        }
    }
    for (i = 0; i < r->primCount; i++) {
        CopyWords(&g_PrimBuf[r->primAt[i]], &r->prims[i], sizeof(Primitive));
    }
    // what's the link's, or the game's, and not the body's: as it is now
    reloaded = B->reloaded, made = B->made, died = B->bodyDied, seen = B->teleportSeen;
    drift = B->driftFrames, loaded = B->bankLoaded, hp = B->partnerHp;
    CopyWords(B, &r->b, sizeof(Body));
    B->reloaded = reloaded, B->made = made, B->bodyDied = died, B->teleportSeen = seen;
    B->driftFrames = drift, B->bankLoaded = loaded, B->partnerHp = hp;
    B->justMade = false;
    CopyWords(BODY_BUF, r->body, BODY_SIZE / 4 * 4);
    if (B->code) {
        StaticsIn();
        StaticsBuf(BuildOf(B->chr), r->statics, STATICS_LOAD);
    }
    if (B->wpnSeq[0] || B->wpnSeq[1]) {
        CopyWords(BODY_WEAPON(s_K, 0), r->weapons, sizeof(r->weapons));
    }
    return true;
}

// Partner k's buttons for frame f: those that came, or a guess (the newest before it that came).
static bool PadKnown(volatile CoopRollIn* in, u32 f) {
    s32 back = in->newest - f;
    return back >= 0 && back < ROLL_PADS && ((in->known >> (f % ROLL_PADS)) & 1);
}
static u16 PadAt(volatile CoopRollIn* in, u32 f, u8* guessed) {
    u32 g;

    if (PadKnown(in, f)) {
        *guessed = 0;
        return in->pads[f % ROLL_PADS];
    }
    *guessed = 1;
    if ((s32)(f - in->newest) > 0 && (s32)(f - in->newest) < ROLL_GUESSES) { // the partner's suggestion
        for (g = f; (s32)(g - in->newest) > 0; g--) {                     // in effect from its frame on
            if ((in->guessed >> (g % ROLL_GUESSES)) & 1) {
                return in->guesses[g % ROLL_GUESSES];
            }
        }
    }
    for (g = (s32)(f - in->newest) > 0 ? in->newest : f; (s32)(in->newest - g) < ROLL_PADS; g--) {
        if (PadKnown(in, g)) {
            return in->pads[g % ROLL_PADS];
        }
    }
    return B->prevPad;
}

// The HP the partner lost in its own game during frame f (0: none, or not known: a guess of none).
static s32 HitAt(volatile CoopRollIn* in, u32 f) {
    u16 before, after;

    if (!PadKnown(in, f) || !PadKnown(in, f - 1)) {
        return 0;
    }
    before = in->hps[(f - 1) % ROLL_PADS];
    after = in->hps[f % ROLL_PADS];
    return before != ROLL_HP_NONE && after != ROLL_HP_NONE && after && before > after ? before - after : 0;
}

// The body's spot (in the room) after frame f, as it ran it, or false (not kept).
static bool SpotAfter(u32 f, s16* x, s16* y) {
    Roll* R = &s_Roll[s_K];
    const RollSnap* r = &ROLL_RING(s_K)[(f + 1) % ROLL_FRAMES];
    const Entity* e;

    if ((s32)(f - R->s) >= 0) { // the body's now (it hasn't got as far as f: as near as it has)
        e = (const Entity*)BODY_BUF;
        *x = e->posX.i.hi + B->scrollX;
        *y = e->posY.i.hi + B->scrollY;
        return true;
    }
    if ((s32)(f + 1 - R->lo) < 0 || r->frame != f + 1) {
        return false;
    }
    e = (const Entity*)r->body;
    *x = e->posX.i.hi + r->b.scrollX;
    *y = e->posY.i.hi + r->b.scrollY;
    return true;
}

// As Pull, but against where the body was at the presence's frame P: what's wrong then is wrong in
// every frame after it too, the kept ones included.
static void RollPull(const CoopPresence* p, u32 P) {
    Roll* R = &s_Roll[s_K];
    Entity* e = (Entity*)BODY_BUF;
    s16 x, y;
    s32 dx, dy, mx, my;
    u32 f;

    if (!SpotAfter(P, &x, &y)) {
        return;
    }
    dx = p->x - x;
    dy = p->y - y;
    R->driftFrames = Ease(dx) || Ease(dy) ? R->driftFrames + 1 : 0;
    if (dx > SNAP_PX || -dx > SNAP_PX || dy > SNAP_PX || -dy > SNAP_PX || R->driftFrames > DRIFT_FRAMES) {
        mx = dx, my = dy;
        e->velocityX = e->velocityY = 0;
        R->driftFrames = 0;
    } else {
        mx = Ease(dx), my = Ease(dy);
    }
    if (!mx && !my) {
        return;
    }
    e->posX.i.hi += mx;
    e->posY.i.hi += my;
    for (f = (s32)(P + 1 - R->lo) > 0 ? P + 1 : R->lo; (s32)(f - R->s) <= 0; f++) {
        RollSnap* r = &ROLL_RING(s_K)[f % ROLL_FRAMES];
        if (r->frame == f) {
            ((Entity*)r->body)->posX.i.hi += mx;
            ((Entity*)r->body)->posY.i.hi += my;
        }
    }
}

// A rollback's correction is drawn sliding out, not jumped: a third a frame, at least 2 px. Past a
// screen, it's a real move (a door): none.
static s16 Slide(s32 d) {
    s32 step = (d < 0 ? -d : d) / 3;

    if (d > 256 || d < -256) {
        return 0;
    }
    step = step < 2 ? 2 : step;
    return d > step ? d - step : d < -step ? d + step : 0;
}

static void RollFrame(const CoopPresence* p, s32 hit) {
    volatile CoopRollIn* in = ROLL_IN(s_K);
    Roll* R = &s_Roll[s_K];
    u32 T = in->target, F = in->newest, P = in->played, f, oldS, from;
    RollSnap* e;
    bool drawn = false, again;
    u16 pad;
    u8 guessed;
    s32 h, ran, wasX, wasY;
    bool rewound;
    u16 start = VSync(1);

    if ((s32)(T - F) > ROLL_LEAD) {
        T = F + ROLL_LEAD;
    }
    if ((s32)(T - P) < 0) {
        T = P;
    }
    if (!R->on || (s32)(T - R->s) > ROLL_FRAMES / 2 || (s32)(R->s - T) > ROLL_FRAMES / 2) {
        // made just now, back from running on the presence, or the partner's frames started over
        // (a reconnect): the body is where the presence was, at its frame
        R->on = true;
        R->s = P;
        R->lo = P + 1;
        R->hit = 0;
        R->driftFrames = 0;
        R->drawX = R->drawY = 0;
    }
    if ((s32)(T - R->s) < 0) {
        T = R->s; // never back: it holds still until the partner's frames catch up
    }
    // A guess the buttons now say was wrong: back to the state before that frame.
    oldS = R->s;
    wasX = ((Entity*)BODY_BUF)->posX.i.hi + B->scrollX; // where it is now, as last run
    wasY = ((Entity*)BODY_BUF)->posY.i.hi + B->scrollY;
    rewound = false;
    from = (s32)(R->lo - (F - ROLL_PADS + 1)) > 0 ? R->lo : F - ROLL_PADS + 1;
    for (f = from; (s32)(f - R->s) <= 0 && (s32)(f - F) <= 0; f++) {
        e = &ROLL_RING(s_K)[f % ROLL_FRAMES];
        if (e->frame != f || !e->guessed || !PadKnown(in, f)) {
            continue;
        }
        if (in->pads[f % ROLL_PADS] == e->pad && HitAt(in, f) == e->hit) {
            e->guessed = 0; // a right guess
            continue;
        }
        if (Restore(f)) {
            R->s = f - 1;
            rewound = true;
            g_CoopRollRewinds++;
        } else { // the guesses stand: the presence's pull puts it right
            g_CoopRollAborts++;
            for (; (s32)(f - oldS) <= 0; f++) {
                ROLL_RING(s_K)[f % ROLL_FRAMES].guessed = 0;
            }
        }
        break;
    }
    RollPull(p, P);
    (void)hit; // its hits come by frame with its buttons (HitAt), not from its status
    R->drawX = Slide(R->drawX);
    R->drawY = Slide(R->drawY);
    for (ran = 0; (s32)(R->s - T) < 0; ran++) {
        f = R->s + 1;
        if (ran && (u16)(VSync(1) - start) > ROLL_LINES) {
            break; // out of time: the rest next frame (one frame always runs)
        }
        again = (s32)(f - oldS) <= 0;
        pad = PadAt(in, f, &guessed);
        h = HitAt(in, f); // where its game said it was hit: on that frame
        if (!PadKnown(in, f - 1)) {
            guessed = 1; // a hit we can't know yet
        }
        g_CoopBodyHits += h && (!again || ROLL_RING(s_K)[f % ROLL_FRAMES].hit != h);
        Keep(f, pad, guessed, h);
        s_SfxLog = &ROLL_RING(s_K)[f % ROLL_FRAMES].sfx;
        if (!again) {
            s_SfxLog->n = 0; // a new frame: nothing heard of it yet
        }
        if ((s32)(f - R->lo) >= ROLL_FRAMES) {
            R->lo = f - ROLL_FRAMES + 1;
        }
        SwapIn();
        Run(p, pad, h, again);
        if (rewound && f == oldS) { // run again to where it was: what the rollback moved it by
            R->drawX += wasX - (PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi);
            R->drawY += wasY - (PLAYER.posY.i.hi + g_Tilemap.scrollY.i.hi);
        }
        if (f == T) {
            Draw();
            drawn = true;
        }
        SwapOut();
        s_SfxLog = NULL;
        R->s = f;
        g_CoopRollFrames += !again;
    }
    g_CoopRollStartLine = start;
    if (!s_K) {
        g_CoopRollDrawn[0] = R->drawX;
        g_CoopRollDrawn[1] = R->drawY;
    }
    if (!drawn) {
        g_CoopRollBehind += R->s != T;
        s_Again = false;
        SwapIn();
        Draw();
        SwapOut();
    }
    if ((u16)(VSync(1) - start) > g_CoopRollLinesMax) {
        g_CoopRollLinesMax = (u16)(VSync(1) - start);
    }
}

// Partner s_K's body (B): made, updated and drawn, or dropped.
static void BodyFrame(void) {
    const CoopPresence* p = Presence();
    s32 t0, hit;
    u16 pad;

    if (g_CoopBodyOff) { // tests: no body (what a game does without one)
        if (B->made) {
            Drop();
        }
        return;
    }
    if (B->made && !Spike() &&
        (!PartnerLive() || !PartnerHere() || Presence()->character != B->chr || B->bodyDied ||
         ((Presence()->flipX & FLIP_TELEPORT_IN) && !B->teleportSeen))) {
        Drop(); // gone (from this room, or for good), or just revived: made again where they are
        B->bodyDied = false;
    }
    B->teleportSeen = PartnerLive() && (Presence()->flipX & FLIP_TELEPORT_IN);
    if (!Spike() && !(PartnerLive() && PartnerHere())) {
        return;
    }
    if (!B->made) {
        u16 m0 = VSync(1);
        Make();
        g_CoopMakeLines = (u16)(VSync(1) - m0);
        B->scrollX = g_Tilemap.scrollX.i.hi;
        B->scrollY = g_Tilemap.scrollY.i.hi;
        if (PartnerLive()) { // where they are (their presence is in room pixels)
            ((Entity*)BODY_BUF)->posX.i.hi = p->x - g_Tilemap.scrollX.i.hi;
            ((Entity*)BODY_BUF)->posY.i.hi = p->y - g_Tilemap.scrollY.i.hi;
        }
        // That's this frame's share: with its first update and drawing too, a frame of play ran
        // past its time (the game then skips a frame: player 1 moved a pixel less).
        B->justMade = true;
        return;
    }
    B->justMade = false;
    t0 = VSync(1);
    if (PartnerLive()) {
        PutStatus();
    }
    ShowPrims();
    hit = HitIn();
    if (RollOn(p)) {
        RollFrame(p, hit);
    } else {
        s_Roll[s_K].on = false;
        pad = !PartnerLive() ? g_CoopSpikePad : Age() <= PARTNER_STALE_FRAMES ? PadIn() : 0;
        SwapIn();
        if (PartnerLive()) {
            Pull(p);
        }
        Run(p, pad, hit, false);
        Draw(); // in the same swap: each one costs some 12 scanlines (M13: the frame's budget)
        SwapOut();
    }
    g_CoopSpikeLines = (u16)(VSync(1) - t0); // a 16-bit counter: its update and drawing
    if (g_CoopSpikeLines > g_CoopSpikeMax) {
        g_CoopSpikeMax = g_CoopSpikeLines;
    }
}

// The body's own hand-weapon entities (DRA runs ids 0xE0-0xEF from hand 0's overlay, 0xF0-0xFF
// from hand 1's) when the weapon isn't ours: not drawn (weapons.c draws the real swing).
static bool HiddenWeapon(const Entity* e) {
    // none left after its update (WeaponsOff), but never drawn; but a weapon it runs (#343)
    return e->entityId >= 0xD0 && !(e->entityId >= 0xE0 && B->wpnRun[(e->entityId - 0xE0) >> 4]);
}

// What the body just drew, from its character's graphics in its bank: textures in F_GAME's
// pages (x 0x200-0x3FF, y 0x100-0x1FF) and palettes in its rows (x 0-0xFF, y 0xF0-0xFF).
static u16 BankTpage(u16 t, u32 bank) { return (t & 0xF) >= 8 && (t & 0x10) ? t | TPAGE_BANK_OF(bank) : t; }
static u16 BankClut(u16 c, u32 bank) {
    u16 y = (c >> 6) & 0x1FF;
    return y >= 0xF0 && y < 0x100 && (c & 0x3F) < 0x10 ? c | CLUT_BANK_OF(bank) : c;
}

u16 PartnerClut(u16 clut) { return B->banked ? BankClut(clut, B->bank) : clut; }

// An Alucard body in an Alucard game draws from player 1's graphics, but its own weapon's (#343)
// from its bank: the polygons drawn with a weapon's palettes (0x110-0x13F).
static bool WeaponClut(u16 c) {
    s32 i;

    for (i = 0; i < 48; i++) {
        if (g_ClutIds[0x110 + i] == c) {
            return true;
        }
    }
    return false;
}
static void WeaponPolys(u32 gt4, u32 gt3) {
    POLY_GT4* q;
    POLY_GT3* t;

    for (; gt4 < g_GpuUsage.gt4; gt4++) {
        q = &g_CurrentBuffer->polyGT4[gt4];
        if (WeaponClut(q->clut)) {
            q->tpage = BankTpage(q->tpage, B->bank);
            q->clut = BankClut(q->clut, B->bank);
        }
    }
    for (; gt3 < g_GpuUsage.gt3; gt3++) {
        t = &g_CurrentBuffer->polyGT3[gt3];
        if (WeaponClut(t->clut)) {
            t->tpage = BankTpage(t->tpage, B->bank);
            t->clut = BankClut(t->clut, B->bank);
        }
    }
}
static void BankPolys(u32 gt4, u32 gt3) {
    for (; gt4 < g_GpuUsage.gt4; gt4++) {
        g_CurrentBuffer->polyGT4[gt4].tpage = BankTpage(g_CurrentBuffer->polyGT4[gt4].tpage, B->bank);
        g_CurrentBuffer->polyGT4[gt4].clut = BankClut(g_CurrentBuffer->polyGT4[gt4].clut, B->bank);
    }
    for (; gt3 < g_GpuUsage.gt3; gt3++) {
        g_CurrentBuffer->polyGT3[gt3].tpage = BankTpage(g_CurrentBuffer->polyGT3[gt3].tpage, B->bank);
        g_CurrentBuffer->polyGT3[gt3].clut = BankClut(g_CurrentBuffer->polyGT3[gt3].clut, B->bank);
    }
}

void PartnerBankPolys(u32 gt4, u32 gt3) { BankPolys(gt4, gt3); }

// The partner tinted, as the puppet was (M1 part 4; agent-default with M13 step 5): two players of
// the same character are told apart. Its sprites drawn plain (raw texture: RenderEntities'
// setShadeTex) are drawn modulated by the tint instead; those with colors of their own keep them.
// M17: each partner a tint of its own (agent-default): blue, red, green.
static const u8 s_Tints[COOP_PARTNERS][3] = {{0x58, 0x68, 0xA8}, {0xA8, 0x60, 0x58}, {0x60, 0xA0, 0x60}};
// Another partner's body here is this one's character.
static bool Twin(void) {
    s32 k;

    for (k = 0; k < COOP_PARTNERS; k++) {
        if (k != s_K && s_Bodies[k].made && s_Bodies[k].chr == B->chr) {
            return true;
        }
    }
    return false;
}

static void Tint(u32 gt4) {
    const u8* c = s_Tints[s_K];
    POLY_GT4* q;

    for (; gt4 < g_GpuUsage.gt4; gt4++) {
        q = &g_CurrentBuffer->polyGT4[gt4];
        if (q->code & 1) { // raw texture
            q->code &= ~1;
            q->r0 = q->r1 = q->r2 = q->r3 = c[0];
            q->g0 = q->g1 = q->g2 = q->g3 = c[1];
            q->b0 = q->b1 = q->b2 = q->b3 = c[2];
        }
    }
}

// The body's primitives, drawn now by themselves (every other one hidden for it), then hidden
// from the game's pass (ShowPrims puts them back before the body's next frame).
// Its primitives (its whip and effects: most of Richter's attacks) go in the game's own pass: the
// textured ones with its graphics are tagged with the bank's texture bit, which RenderPrimitives
// copies into their polygons; after it, PartnerAfterPrims gives those polygons the bank's palette
// too and takes the tag off again. (A pass of our own, with every other primitive hidden and
// shown again, cost some 40 scanlines a frame: the mixed soak missed frames.)
// The body's primitives moved with a rollback's correction for the game's pass, and back before
// its next frame (ShowPrims): what's kept and run is where the body really is.
static void ShiftPrim(Primitive* p, s32 dx, s32 dy) {
    switch (p->type & 0xF) {
    case PRIM_G4:
    case PRIM_GT4:
        p->x3 += dx;
        p->y3 += dy;
    case PRIM_GT3:
        p->x2 += dx;
        p->y2 += dy;
    case PRIM_LINE_G2:
        p->x1 += dx;
        p->y1 += dy;
    case PRIM_TILE:
    case PRIM_SPRT:
        p->x0 += dx;
        p->y0 += dy;
    }
}
static void DrawShift(s16 dx, s16 dy) {
    Roll* R = &s_Roll[s_K];
    s32 i;

    for (i = 0; i < B->primCount && (dx || dy); i++) {
        ShiftPrim(&g_PrimBuf[B->prims[i]], dx, dy);
    }
    R->shiftX = B->primCount ? dx : 0;
    R->shiftY = B->primCount ? dy : 0;
}
static void UndoShift(void) {
    Roll* R = &s_Roll[s_K];
    s32 i;

    if (R->shiftX || R->shiftY) {
        for (i = 0; i < B->primCount; i++) {
            ShiftPrim(&g_PrimBuf[B->prims[i]], -R->shiftX, -R->shiftY);
        }
    }
    R->shiftX = R->shiftY = 0;
}

static s16 s_Tagged[PRIMS * COOP_PARTNERS]; // every body's (one pass draws them all)
static s32 s_TagCount;

static void TagPrims(void) {
    Primitive* p;
    s32 i;

    FindPrims();
    HideFlashes();
    for (i = 0; i < B->primCount; i++) {
        p = &g_PrimBuf[B->prims[i]];
        B->primHidden[i] = false;
        if ((p->type == PRIM_GT4 || p->type == PRIM_GT3) && !(p->tpage & TPAGE_BANKS) &&
            BankTpage(p->tpage, B->bank) != p->tpage && s_TagCount < LEN(s_Tagged)) {
            p->tpage |= TPAGE_BANK_OF(B->bank);
            s_Tagged[s_TagCount++] = B->prims[i];
        }
    }
}

void PartnerAfterPrims(u32 gt4, u32 gt3) {
    s32 i;

    if (!s_TagCount) {
        return;
    }
    for (; gt4 < g_GpuUsage.gt4; gt4++) {
        u16 t = g_CurrentBuffer->polyGT4[gt4].tpage;
        if (t & TPAGE_BANKS) {
            g_CurrentBuffer->polyGT4[gt4].clut = BankClut(g_CurrentBuffer->polyGT4[gt4].clut, TPAGE_BANK_IS(t));
        }
    }
    for (; gt3 < g_GpuUsage.gt3; gt3++) {
        u16 t = g_CurrentBuffer->polyGT3[gt3].tpage;
        if (t & TPAGE_BANKS) {
            g_CurrentBuffer->polyGT3[gt3].clut = BankClut(g_CurrentBuffer->polyGT3[gt3].clut, TPAGE_BANK_IS(t));
        }
    }
    for (i = 0; i < s_TagCount; i++) {
        g_PrimBuf[s_Tagged[i]].tpage &= ~TPAGE_BANKS;
    }
    s_TagCount = 0;
}

// Draws the partner, right after its update, with its slots still swapped in: everything else
// hidden (animCurFrame 0, which RenderEntities skips), drawn, and all put back.
static void Draw(void) {
    static u16 frames[256];
    u32 gt4 = g_GpuUsage.gt4, gt3 = g_GpuUsage.gt3;
    s32 i;
    s16 ox = s_Roll[s_K].on ? s_Roll[s_K].drawX : 0, oy = s_Roll[s_K].on ? s_Roll[s_K].drawY : 0;

    for (i = 0; i < 64 && (ox || oy); i++) { // a rollback's correction sliding out (RollFrame)
        if (!i || g_Entities[i].entityId || (i <= E_AFTERIMAGE_3 && B->otherChar)) {
            g_Entities[i].posX.i.hi += ox;
            g_Entities[i].posY.i.hi += oy;
        }
    }
    frames[0] = PLAYER.animCurFrame;
    PLAYER.animCurFrame = MAR_SAFE_FRAME(B->chr, &PLAYER);
    for (i = 1; i < 256; i++) {
        frames[i] = g_Entities[i].animCurFrame;
        if (i >= 64 || HiddenWeapon(&g_Entities[i])) {
            g_Entities[i].animCurFrame = 0;
        }
    }
    RenderEntities();
    for (i = 0; i < 256; i++) {
        g_Entities[i].animCurFrame = frames[i];
    }
    for (i = 0; i < 64 && (ox || oy); i++) {
        if (!i || g_Entities[i].entityId || (i <= E_AFTERIMAGE_3 && B->otherChar)) {
            g_Entities[i].posX.i.hi -= ox;
            g_Entities[i].posY.i.hi -= oy;
        }
    }
    if ((!B->otherChar || Twin()) && !(g_CoopLink.options & OPT_NO_TINT)) { // only two of a kind need telling apart
        Tint(gt4);
    }
    if (B->banked) {
        BankPolys(gt4, gt3);
    } else if (B->wpnRun[0] || B->wpnRun[1]) {
        WeaponPolys(gt4, gt3);
    }
    if (B->banked) { // its whip and effects, drawn by the game from the bank
        TagPrims();
    } else { // the game draws them (the same graphics): only its screen flashes kept out
        FindPrims();
        HideFlashes();
        B->primCount = 0; // nothing of ours to give back but the flashes
    }
    DrawShift(ox, oy);
    if (PartnerLive()) { // its familiar, beside the body (in RAM now: the copy holds player 1)
        FamiliarDraw(s_K, PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi - Presence()->x,
                     PLAYER.posY.i.hi + g_Tilemap.scrollY.i.hi - Presence()->y);
    }
}

// Where the partner is (the harness checks it moves as its buttons say).
const Entity* PartnerBody(void) { return B->made ? (const Entity*)BODY_BUF : NULL; }

// Which partner's body the calls above are about (weapons.c draws each one's swings). PartnerFrame
// leaves partner 0's.
void PartnerSelect(s32 k) {
    if (!s_BodiesSet) {
        SetBodies();
    }
    s_K = k;
    B = &s_Bodies[k];
}
