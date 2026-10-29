// M13 (design/M13-partner-player.md): the partner as a real second player. Each frame, after the
// game has updated player 1, the partner's copy of "the player" is swapped into RAM, the game's
// own player update runs on it with the partner's buttons (CoopLink.partnerPad, played out with
// its presence), and it's swapped back out. It exists while the partner is in our room, and is
// pulled to their real spot when it drifts past SNAP_PX. Cosmetic: no hit detection runs for it.
// It's how the partner is drawn (M13 step 5: the puppet is gone). Without a partner, there's no
// body, except in the harness's spike test (OPT_PARTNER_SIM): a copy of player 1 on g_CoopSpikePad.
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
    {STATUS_A, STATUS_A_SIZE},          // g_Status: hp .. statsTotal (the partner's: PutStatus)
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
#define BODY_SIZE (64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4) + 0x280 + 8 + 4 + 0x48 + 0x34 + 0x30 + 0x40 + 0x40 + \
                   0xC + 0x8 + 0x100 + 0x4 + 0x4 + 0x4 + 0x4)

// A partner who runs its own player code (Richter, Maria), or an Alucard partner in their game:
// what DRA reads at 0x8013C000 (g_PlOvl: the update functions, then the body's sprite table, which
// ends at 0x8013C334 in our Richter's file and 0x8013C388 in Alucard's ARC_F.BIN) and the four
// sprite banks a Richter or Maria init installs. Swapped with player 1's for its frames.
#define HDR_ADDR 0x8013C000
#define HDR_SIZE 0x388
static u32 s_Hdr[HDR_SIZE / 4];
#define BANKS 8 // sprite banks 0x10-0x17: Richter's 0x10-0x13, Maria's 0x10-0x16, the off-hand's 0x17
static u32 s_Banks[BANKS];
static u32 s_Char;    // CHAR_* of the body
static bool s_Code;   // it runs its own player code (not DRA's Alucard)
static bool s_AluHere; // an Alucard partner in another character's game (DRA's Alucard, ARC_F swapped in)
static Unkstruct_8006C3C4 s_PalOps[LEN(D_8006C3C4)]; // DRA's palette operations, kept from it
static bool s_Banked; // its graphics are in VRAM's second bank (another character than ours)
static s32 s_SavedChar;
static u32 s_SavedRandom;
static u32 s_BankLoaded = 0xFF; // CHAR_* whose graphics are in the second bank
static bool s_Reloaded; // the stage reloaded since Make (its primitives are gone with it)
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
static u32 s_PartnerSeed = 1;
static bool s_RandLooked;

// Once, at boot (coop.c: its first frame, while the logos show): a 64KB scan is too slow for a
// frame of play (the first body's frame lagged a frame, and player 1 with it).
void PartnerBoot(void) {
    u32 x, y, s1, s0, *w;

    if (s_RandLooked) {
        return;
    }
    s_RandLooked = true;
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
        *g_CoopRandSeed = s_PartnerSeed;
        s_PartnerSeed = t;
    }
}

static void RandOn(void) {
    u32 t;

    if (g_CoopRandSeed) {
        t = *g_CoopRandSeed;
        *g_CoopRandSeed = s_PartnerSeed;
        s_PartnerSeed = t;
    }
}
u32 g_CoopSpikeBody[BODY_SIZE / 4]; // the partner's copy, while player 1's is in RAM (its entity 0 first)
static bool s_Made;
static u16 s_PrevPad;
static s16 s_ScrollX, s_ScrollY; // the camera when the copy was last swapped out
#define SNAP_PX 48

u32 g_CoopSpikePad;   // harness: the partner's buttons (PAD_*)
u32 g_CoopSpikeLines; // the last partner frame's cost, in scanlines (263 a frame)
u32 g_CoopSpikeMax;   // the most it has cost
u32 g_CoopMakeLines;  // what making the body last cost, in scanlines (tests)
static bool s_JustMade; // made this frame: its update and drawing start next frame

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

static void WeaponsOff(void) {
    s32 hand, k;

    for (hand = 0; hand < 2; hand++) {
        for (k = 0; k < WEAPON_HDR_WORDS; k++) {
            s_WeaponHdr[hand][k] = WEAPON_HDR(hand)[k];
            WEAPON_HDR(hand)[k] = (u32)(k == 6 ? (void*)NoWeaponId : (void*)NoWeapon); // 6: GetWeaponId
        }
    }
    s_WeaponEntity = g_CoopWeaponEntity;
    g_CoopWeaponEntity = (void (*)(Entity*))NoWeapon;
}

static void WeaponsOn(void) {
    s32 hand, k;

    for (hand = 0; hand < 2; hand++) {
        for (k = 0; k < WEAPON_HDR_WORDS; k++) {
            WEAPON_HDR(hand)[k] = s_WeaponHdr[hand][k];
        }
    }
    g_CoopWeaponEntity = s_WeaponEntity;
}

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

// The partner's sounds (step 4): the requests its frame added to DRA's ring are quieter (the host's
// setting) and panned to where it is. A sound of the player's own bank (VAB 1: Alucard's or
// Richter's and Maria's voice) is another character's here: dropped (volume 0).
extern s16 g_sfxRingBufferWritePos;            // DRA
extern SfxRingBufferItem g_SfxRingBuffer[0x100]; // DRA
extern Unkstruct_800BF554 g_SfxData[];         // DRA
#define PARTNER_VOL 60 // % of its volume, unless the host says otherwise
#define PLAYER_VAB 1
static s16 s_SfxPos;

static void PartnerSounds(void) {
    s32 pct = (g_CoopLink.control >> CONTROL_PARTNER_VOL_SHIFT) & 0xFF, vol, pan;
    SfxRingBufferItem* it;
    s16 pos;

    pct = pct ? pct : PARTNER_VOL;
    pan = (PLAYER.posX.i.hi - 128) / 16;
    pan = pan < -8 ? -8 : pan > 8 ? 8 : pan;
    for (pos = s_SfxPos; pos != g_sfxRingBufferWritePos; pos = (pos + 1) & 0xFF) {
        it = &g_SfxRingBuffer[pos];
        if (s_Char != CharacterLoaded() && g_SfxData[it->sndId].vabid == PLAYER_VAB) {
            it->sndVol = 0;
            continue;
        }
        vol = it->sndVol == 0xFFFF ? 0x7F : it->sndVol;
        it->sndVol = (vol * pct / 100) & 0x7F;
        it->sndPan = pan;
    }
}

// Exchanges the game's copy with the partner's, a word at a time (region 0 first: the slots).
static void Swap(void) {
    u32* body = g_CoopSpikeBody;
    s32 i;
    u32 k, t;

    if (s_Code || s_AluHere) {
        u32* ram = (u32*)HDR_ADDR;
        for (k = 0; k < HDR_SIZE / 4; k++) {
            t = ram[k];
            ram[k] = s_Hdr[k];
            s_Hdr[k] = t;
        }
        ram = (u32*)g_api.o.spriteBanks + 16;
        for (k = 0; k < BANKS; k++) {
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
static void LoadGraphics(const u8* file, const u8* palettes) {
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
    LoadImage(&r, (u_long*)palettes);
    DrawSync(0);
}

// Alucard's ARC_F.BIN as DRA reads it, from CoopBoot's copy (linked at 0x8013C000): its header
// words point at the sprite table (0x8013C020, swapped in as it is), except the bat's table, and
// the 218 sprite and 6 bat sprite pointers are rebased onto the copy.
#define ALU_SHEETS 218
#define ALU_BATS 6
static u32 s_AluBats[ALU_BATS];

static void AluHeader(void) {
    const u32* arc = (const u32*)ARC_F_ADDR;
    u32 delta = ARC_F_ADDR - HDR_ADDR, k;

    for (k = 0; k < HDR_SIZE / 4; k++) {
        s_Hdr[k] = arc[k];
    }
    for (k = 8; k < 8 + ALU_SHEETS; k++) {
        if (s_Hdr[k]) {
            s_Hdr[k] += delta;
        }
    }
    for (k = 0; k < ALU_BATS; k++) {
        s_AluBats[k] = ((const u32*)(arc[1] + delta))[k] + delta;
    }
    s_Hdr[1] = (u32)s_AluBats;
}

// DRA's own palette load for Alucard (op 0x16: palettes 0x100-0x10D, src/dra/4A538.c), into the
// second bank, as his init would have them in the first.
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
        r.y = ((clut >> 6) & 0x1FF) | VRAM_BANK;
        r.w = 16;
        r.h = 1;
        LoadImage(&r, (u_long*)(colors + k * 16));
        DrawSync(0);
    }
}

// The partner starts as a copy of player 1, a little to the right.
#define DRAW_OFS (64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4)) // g_PlayerDraw in the copy

static bool s_TeleportSeen; // the partner's FLIP_TELEPORT_IN, last frame
static s32 s_PartnerHp = -1; // its HP, as its status last said (a drop: it was hit in its game)
u32 g_CoopBodyHits; // hits given to the body (tests read it: coop.map)
u32 g_CoopBodyOff; // tests: no partner body (it's drawn by nothing then)
u32 g_CoopBodyTeleports; // bodies made with the partner's teleport-in (tests read it: coop.map)

static void Make(void) {
    u32* body = g_CoopSpikeBody;
    PlayerDraw* draw;
    s32 i;
    u32 k;
    // just revived: its init plays its character's teleport-in (arrive.c's TeleportIn)
    s32 how = PartnerLive() && (g_CoopLink.partner.flipX & FLIP_TELEPORT_IN) ? 6 : 0;
    s32 saved;

    g_CoopBodyTeleports += how != 0;

    for (i = 0; i < LEN(s_Regions); i++) {
        u32* ram = (u32*)s_Regions[i].addr;
        for (k = 0; k < s_Regions[i].len / 4; k++) {
            *body++ = ram[k];
        }
    }
    ((Entity*)g_CoopSpikeBody)->posX.i.hi += 32;
    s_Char = PartnerLive() ? g_CoopLink.partner.character : CHAR_ALUCARD;
    s_Code = s_Char != CHAR_ALUCARD;
    s_AluHere = !s_Code && CharacterLoaded() != CHAR_ALUCARD;
    // A partner build's own uploads always go to the second bank (coop_ric.h): it draws from there.
    s_Banked = s_Code || s_Char != CharacterLoaded();
    s_Reloaded = false;
    s_PartnerHp = -1; // its first status here isn't a hit
    s_ScrollX = g_Tilemap.scrollX.i.hi; // for SwapIn: no camera move to apply to the copy
    s_ScrollY = g_Tilemap.scrollY.i.hi;
    if (s_Banked && s_BankLoaded != s_Char) { // before the init: Maria's uploads her palettes
        if (s_Char == CHAR_ALUCARD) {
            LoadGraphics((const u8*)FGAME_GFX_ADDR, (const u8*)FGAME_PAL_ADDR);
            AluPalettes();
        } else {
            LoadGraphics((const u8*)FGAME2_ADDR, (const u8*)FGAME2_ADDR + 0x40000); // Richter's; Maria's runs on it too
        }
        s_BankLoaded = s_Char;
        FamiliarReload(); // the strips held the partner's familiar too
    }
    if (!s_Code) { // DRA's Alucard, from his own init, with nothing of player 1's (slots 1-63
                   // hold player 1's afterimages, familiar, weapons: their primitives are player 1's)
        Entity* pl = (Entity*)g_CoopSpikeBody;
        s16 x = pl->posX.i.hi, y = pl->posY.i.hi;

        if (s_AluHere) {
            AluHeader();
            for (k = 0; k < BANKS; k++) {
                s_Banks[k] = ((u32*)g_api.o.spriteBanks)[16 + k];
            }
        }
        for (k = 0xBC / 4; k < 64 * 0xBC / 4; k++) {
            g_CoopSpikeBody[k] = 0;
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
        for (k = 0; k < BANKS; k++) {
            s_Banks[k] = banks[k];
        }
        for (k = 0xBC / 4; k < 64 * 0xBC / 4; k++) { // slots 1-63: player 1's (their primitives too)
            g_CoopSpikeBody[k] = 0;
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
    s_SfxPos = g_sfxRingBufferWritePos;
    WeaponsOff();
    RandOff();
    g_CoopCharacter = s_Code ? PLAYER_RICHTER : PLAYER_ALUCARD; // Maria's runs as Richter's too
    if (!s_Code) { // his palette operations would work on player 1's palettes: none kept
        for (i = 0; i < LEN(D_8006C3C4); i++) {
            s_PalOps[i] = D_8006C3C4[i];
        }
    }
    if (s_Code) {
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

// Since the body never runs the weapons' code (WeaponsOff), its swings always come from the link.
bool PartnerWeaponDiffers(s32 hand) { return true; }

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
    }
    PartnerSounds(); // the body is still in RAM: its spot pans them
    RandOn();
    WeaponsOn();
    g_CoopCharacter = s_SavedChar;
    g_randomNext = s_SavedRandom;
    if (!s_Code) {
        s32 i;
        for (i = 0; i < LEN(D_8006C3C4); i++) {
            D_8006C3C4[i] = s_PalOps[i];
        }
    }
    Swap();
}

static bool PartnerLive(void) { return g_CoopLink.partnerAge <= PARTNER_STALE_FRAMES; }

// The partner is in this room, in play, as a character we can run: Alucard (DRA's code), Richter or
// Maria (their partner builds), in any game.
static bool PartnerHere(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    return p->stage == g_StageId && p->roomLeft == g_Tilemap.left && p->roomTop == g_Tilemap.top &&
           (p->flags & PRESENCE_IN_PLAY) && g_PlayableCharacter == 0 &&
           (p->character == CHAR_ALUCARD || PartnerCode(p->character));
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

// A primitive of the body's that covers the screen (its teleport-in's white flash): that's this
// game's player's screen, not the body's to flash. Hidden from every pass, given back after.
#define FLASHES 8
static s16 s_Flash[FLASHES];
static s32 s_FlashCount;

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

    for (i = 0; i < s_PrimCount && s_FlashCount < FLASHES; i++) {
        p = &g_PrimBuf[s_Prims[i]];
        if (!(p->drawMode & DRAW_HIDE) && CoversScreen(p)) {
            p->drawMode |= DRAW_HIDE;
            s_Flash[s_FlashCount++] = s_Prims[i];
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
    for (i = 0; i < s_FlashCount; i++) {
        g_PrimBuf[s_Flash[i]].drawMode &= ~DRAW_HIDE;
    }
    s_PrimCount = 0;
    s_FlashCount = 0;
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

// The harness's spike test only (OPT_PARTNER_SIM, no partner): a copy of player 1 on g_CoopSpikePad.
static bool Spike(void) { return (g_CoopOptions & OPT_PARTNER_SIM) && !PartnerLive(); }

bool PartnerSimulated(void) {
    return s_Made && (Spike() || (PartnerLive() && PartnerHere()));
}

void PartnerFrame(void) {
    const CoopPresence* p = &g_CoopLink.partner;
    Pad pad0;
    Entity* cur;
    s32 i;
    s32 t0;
    u16 pad;

    if (ArriveCardSaving()) {
        return; // the game is frozen while its card is written (the card and pads share the port)
    }
    if (g_GameState != Game_Play || g_GameStep != Play_Default || g_GameEngineStep == Engine_Init) {
        // A load (a stage, a save, a teleport's arrival) frees every primitive and replaces the
        // stage's sprite-bank table: the body goes with it, and is made again in play. Engine_Init
        // is the load's end, in Play_Default: it frees every primitive too (a body made before it
        // lost its own, walked the chains that replaced them to their end and wrote through NULL:
        // the BIOS's pad driver died).
        s_Reloaded = true;
        s_Made = false;
        s_PrimCount = 0;
        s_FlashCount = 0;
        return;
    }
    if (g_CoopBodyOff) { // tests: no body (what a game does without one)
        if (s_Made) {
            Drop();
        }
        return;
    }
    if (s_Made && !Spike() &&
        (!PartnerLive() || !PartnerHere() || g_CoopLink.partner.character != s_Char ||
         ((g_CoopLink.partner.flipX & FLIP_TELEPORT_IN) && !s_TeleportSeen))) {
        Drop(); // gone (from this room, or for good), or just revived: made again where they are
    }
    s_TeleportSeen = PartnerLive() && (g_CoopLink.partner.flipX & FLIP_TELEPORT_IN);
    if (!Spike() && !(PartnerLive() && PartnerHere())) {
        return;
    }
    if (!s_Made) {
        u16 m0 = VSync(1);
        Make();
        g_CoopMakeLines = (u16)(VSync(1) - m0);
        s_ScrollX = g_Tilemap.scrollX.i.hi;
        s_ScrollY = g_Tilemap.scrollY.i.hi;
        if (PartnerLive()) { // where they are (their presence is in room pixels)
            ((Entity*)g_CoopSpikeBody)->posX.i.hi = p->x - g_Tilemap.scrollX.i.hi;
            ((Entity*)g_CoopSpikeBody)->posY.i.hi = p->y - g_Tilemap.scrollY.i.hi;
        }
        // That's this frame's share: with its first update and drawing too, a frame of play ran
        // past its time (the game then skips a frame: player 1 moved a pixel less).
        s_JustMade = true;
        return;
    }
    s_JustMade = false;
    pad = PartnerLive() ? g_CoopLink.partnerPad : g_CoopSpikePad;
    t0 = VSync(1);
    if (PartnerLive()) {
        PutStatus();
    }
    ShowPrims();
    SwapIn();
    // Hit in its own game (its HP dropped): its own hit reaction here, its own code's knockback
    // and voice, from the same HP to the same HP (cosmetic: the body's status is the partner's).
    if (PartnerLive() && ((const CoopStatus*)STATUS_PARTNER_ADDR)->magic == STATUS_MAGIC) {
        s32 hp = *(const s32*)((const CoopStatus*)STATUS_PARTNER_ADDR)->a; // g_Status.hp
        if (s_PartnerHp > hp && hp > 0) {
            g_Status.hp = s_PartnerHp;
            PLAYER.hitParams = DAMAGEKIND_1;
            PLAYER.hitPoints = s_PartnerHp - hp + g_Status.defenseEquip;
            g_CoopBodyHits++;
        }
        s_PartnerHp = hp;
    }
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
    for (i = 1; i < 64; i++) { // its weapons' and familiar's entities: not its to run (WeaponsOff)
        if (g_Entities[i].entityId >= 0xD0) {
            DestroyEntity(&g_Entities[i]);
        }
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
    return e->entityId >= 0xD0; // none left after its update (WeaponsOff), but never drawn
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

void PartnerBankPolys(u32 gt4, u32 gt3) { BankPolys(gt4, gt3); }

// The partner tinted, as the puppet was (M1 part 4; agent-default with M13 step 5): two players of
// the same character are told apart. Its sprites drawn plain (raw texture: RenderEntities'
// setShadeTex) are drawn modulated by the tint instead; those with colors of their own keep them.
#define TINT_R 0x58
#define TINT_G 0x68
#define TINT_B 0xA8
static void Tint(u32 gt4) {
    POLY_GT4* q;

    for (; gt4 < g_GpuUsage.gt4; gt4++) {
        q = &g_CurrentBuffer->polyGT4[gt4];
        if (q->code & 1) { // raw texture
            q->code &= ~1;
            q->r0 = q->r1 = q->r2 = q->r3 = TINT_R;
            q->g0 = q->g1 = q->g2 = q->g3 = TINT_G;
            q->b0 = q->b1 = q->b2 = q->b3 = TINT_B;
        }
    }
}

// The body's primitives, drawn now by themselves (every other one hidden for it), then hidden
// from the game's pass (ShowPrims puts them back before the body's next frame).
static void DrawPrims(void) {
    static u8 s_Others[MAX_PRIM_COUNT]; // DRAW_HIDE we set on others for our pass
    s32 flash; // D_8003C0EC[3]: a screen flash's frames left (r, g, b before it)
    u32 gt4 = g_GpuUsage.gt4, gt3 = g_GpuUsage.gt3;
    s32 i;

    FindPrims();
    HideFlashes();
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
    flash = D_8003C0EC[3]; // a screen flash: the game's own pass draws it, and counts it down
    D_8003C0EC[3] = 0;
    RenderPrimitives();
    D_8003C0EC[3] = flash;
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

    if (!PartnerSimulated() || g_GameState != Game_Play || g_GameStep != Play_Default || s_JustMade ||
        g_GameEngineStep == Engine_Init || ArriveCardSaving()) {
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
    Tint(gt4);
    if (s_Banked) {
        BankPolys(gt4, gt3);
    }
    if (s_Banked) { // its whip and effects (most of Richter's attacks are primitives), from the bank
        DrawPrims();
    } else { // the game draws them (the same graphics): only its screen flashes kept out
        FindPrims();
        HideFlashes();
        s_PrimCount = 0; // nothing of ours to give back but the flashes
    }
    if (PartnerLive()) { // its familiar, beside the body (in RAM now: the copy holds player 1)
        FamiliarDraw(PLAYER.posX.i.hi + g_Tilemap.scrollX.i.hi - g_CoopLink.partner.x,
                     PLAYER.posY.i.hi + g_Tilemap.scrollY.i.hi - g_CoopLink.partner.y);
    }
    SwapOut();
}

// Where the partner is (the harness checks it moves as its buttons say).
const Entity* PartnerBody(void) { return s_Made ? (const Entity*)g_CoopSpikeBody : NULL; }
