// VRAM uploads for a shared room's guest (playtest 2 prep: a relic's "Obtained ..." box was empty
// on the guest's screen).
//
// Some stage entities write into VRAM as they run: the text of an item's or relic's message
// box, palette fades. The guest doesn't run them, so it gets their primitives (from the
// snapshot) but not the picture they show. The module patches libgpu's LoadImage (main.exe,
// always resident) to come here; uploads made by the stage overlay's code while this game is a
// room's authority are recorded and sent with the snapshot, and the guest makes them too.
// Uploads from DRA (the player's sprite frames, every frame) are each game's own and never sent,
// except a pickup's icon (issue 100): stages load it through DRA's LoadEquipIcon, into a slot the
// guest's copy of the pickup draws from. LoadEquipIcon skips what its slot already holds, so in
// play the authority clears that record each frame, and a guest who's just arrived is sent every
// icon again.
//
// The guest keeps the icons it's sent (#354: a pickup drawn as "NOW MAKING", a relic as a sword).
// Closing a menu or the save screen puts every slot back from DRA's record of what each slot
// should hold (func_800EB6B4), and the guest's record never had the authority's pickups: icon 0,
// DRA's "NOW MAKING" placeholder, filled them all. Its restore comes here instead, and puts back
// what the authority sent.
#define COOP_MODULE
#include <game.h>
#include "overlay_table.h"
#include "vram.h"

void FlushCache(void); // main.exe

// libgpu (main.exe): LoadTPage and LoadClut upload through LoadImage, so they're patched too,
// to know when their caller was the stage. Each entry: where, and its first instruction.
#define LOAD_IMAGE ((u32*)0x80012B24) // int LoadImage(RECT* rect, u_long* p)
#define LOAD_IMAGE_FIRST 0x27BDFFE0   // addiu sp, sp, -32
#define LOAD_TPAGE ((u32*)0x8001112C) // u_short LoadTPage(u_long* pix, tp, abr, x, y, w, h)
#define LOAD_TPAGE_FIRST 0x27BDFFD0   // addiu sp, sp, -48
#define LOAD_CLUT ((u32*)0x80011218)  // u_short LoadClut(u_long* clut, int x, int y)
#define LOAD_CLUT_FIRST 0x27BDFFD8    // addiu sp, sp, -40
u16 GetTPage(s32 tp, s32 abr, s32 x, s32 y); // main.exe
u16 GetClut(s32 x, s32 y);                    // main.exe
#define STAGE_CODE 0x80180000         // stage overlays load here
#define LOAD_EQUIP_ICON 0x800EB534     // DRA (src/dra/4AEA4.c), up to the next function
#define LOAD_EQUIP_ICON_END 0x800EB6B4
#define ICON_SLOTS 32
#define NO_ICON 0xFFFF
extern u16 D_801374F8[], D_80137538[]; // DRA: the icon and palette each slot holds
extern u16 D_80137478[], D_801374B8[]; // DRA: what each slot should hold (put back after a menu)
#define RESTORE_ICONS ((u32*)0x800EB6B4) // DRA's func_800EB6B4: every slot from D_80137478
#define RESTORE_ICONS_FIRST 0x27BDFFE0
#define ICON_X 0x280 // slot i: x ICON_X + (i & 7) * 4, y ICON_Y + (i / 8) * 16, 4 x 16 (4bpp)
#define ICON_Y 0x180
#define ICON_PAL_Y 0xFD // palettes: slot i's 16 colours at row 0xFD + i / 16, x (i % 16) * 16
#define ICON_WORDS (4 * 16)
#define J(target) (0x08000000 | (((u32)(target) & 0x0FFFFFFF) >> 2))

// libgpu's queue (src/main/psxsdk/libgpu/sys.c): LoadImage is addque2(dws, rect, 8, p)
typedef struct {
    u32 unk0[2];
    s32 (*addque2)(s32 queue, void* param, s32 size, void* data);
    u32 unkC[5];
    s32 dws;
} GpuQueue;
#define GPU_QUEUE (*(GpuQueue**)0x8002C260)

static u8 s_Uploads[VRAM_UPLOADS_MAX] __attribute__((aligned(4)));
static s32 s_Size;
static bool s_Record;
static bool s_Patched;
static bool s_FromStage; // inside LoadTPage / LoadClut called by the stage

static u16 s_Icons[ICON_SLOTS], s_IconPals[ICON_SLOTS]; // what each slot held
static s32 s_Resend;

// guest: the icons and palettes the authority sent, by slot
static u16 s_SentPix[ICON_SLOTS][ICON_WORDS];
static u16 s_SentPal[ICON_SLOTS][COLORS_PER_PAL];
static u32 s_SentIcons; // a bit per slot holding a sent icon
static u32 s_SentRoom;  // the room they were sent in (stage, left, top)
#define ROOM_NOW ((u32)g_StageId << 16 | (u32)(u8)g_Tilemap.left << 8 | (u8)g_Tilemap.top)

static bool StageCaller(u32 caller) {
    const OverlayInfo* ovl;

    if (caller >= LOAD_EQUIP_ICON && caller < LOAD_EQUIP_ICON_END && g_GameEngineStep == Engine_Normal) {
        return true;
    }
    return caller >= STAGE_CODE && (ovl = FindOverlay(g_StageId)) && caller < ovl->bssStart;
}

static void Record(RECT* rect, u_long* p) {
    s32 bytes = rect->w * rect->h * 2;

    if (bytes <= 0 || s_Size + sizeof(RECT) + ((bytes + 3) & ~3) > VRAM_UPLOADS_MAX) {
        return; // too much this frame: the rest isn't sent
    }
    __builtin_memcpy(s_Uploads + s_Size, rect, sizeof(RECT));
    __builtin_memcpy(s_Uploads + s_Size + sizeof(RECT), p, bytes);
    s_Size += sizeof(RECT) + ((bytes + 3) & ~3);
}

// LoadImage's first instruction jumps here, so $ra is still the original caller's.
s32 CoopLoadImage(RECT* rect, u_long* p) {
    if (s_Record && (s_FromStage || StageCaller((u32)__builtin_return_address(0)))) {
        Record(rect, p);
    }
    return GPU_QUEUE->addque2(GPU_QUEUE->dws, rect, sizeof(RECT), p);
}

// Copies of libgpu's own (src/main/psxsdk/libgpu/ext.c). Reached by a jump, so the stack
// arguments (y, w, h) are where the caller put them.
u16 CoopLoadTPage(u_long* pix, s32 tp, s32 abr, s32 x, s32 y, s32 w, s32 h) {
    RECT rect;

    rect.x = x;
    rect.y = y;
    rect.h = h;
    rect.w = tp == 0 ? w / 4 : tp == 1 ? w / 2 : w;
    s_FromStage = StageCaller((u32)__builtin_return_address(0));
    CoopLoadImage(&rect, pix);
    s_FromStage = false;
    return GetTPage(tp, abr, x, y);
}

u16 CoopLoadClut(u_long* clut, s32 x, s32 y) {
    RECT rect;

    rect.x = x;
    rect.y = y;
    rect.w = 0x100;
    rect.h = 1;
    s_FromStage = StageCaller((u32)__builtin_return_address(0));
    CoopLoadImage(&rect, clut);
    s_FromStage = false;
    return GetClut(x, y);
}

// DRA's restore (func_800EB6B4), with the slots a guest was sent put back as sent.
void CoopRestoreIcons(void) {
    RECT r;
    s32 i, k;

    for (i = 0; i < ICON_SLOTS; i++) {
        if (!(s_SentIcons & (1 << i))) {
            g_api.LoadEquipIcon(D_80137478[i], D_801374B8[i], i);
            continue;
        }
        r.x = ICON_X + (i & 7) * 4;
        r.y = ICON_Y + (i / 8) * 16;
        r.w = 4;
        r.h = 16;
        LoadImage(&r, (u_long*)s_SentPix[i]);
        for (k = 0; k < COLORS_PER_PAL; k++) {
            g_Clut[1][i * COLORS_PER_PAL + k + 0xD00] = s_SentPal[i][k];
        }
        D_801374F8[i] = D_80137538[i] = NO_ICON; // DRA's own next load of this slot isn't skipped
    }
    LoadClut((u_long*)&g_Clut[1][0xD00], 0, ICON_PAL_Y);
    LoadClut((u_long*)&g_Clut[1][0xE00], 0, ICON_PAL_Y + 1);
}

// A guest's slots are the authority's. Its own code still loads icons into them (an entity it
// runs itself each frame, its own room for the frames after a menu), by its own numbering: while
// it's a guest, outside a menu, those loads are dropped (CoopLoadEquipIcon), and every 10 frames
// the icons it was sent go back in, for anything that got past.
#define REAPPLY_EVERY 10
#define LOAD_EQUIP_ICON_FIRST 0x27BDFFC8 // addiu sp, sp, -56
static bool s_Guest;
static u32 s_IconTramp[4]; // LoadEquipIcon's first two instructions, then a jump to its third

static void Reapply(void) {
    RECT r;
    s32 i, k;

    if (!s_SentIcons || s_SentRoom != ROOM_NOW) {
        return;
    }
    for (i = 0; i < ICON_SLOTS; i++) {
        if (s_SentIcons & (1 << i)) {
            r.x = ICON_X + (i & 7) * 4;
            r.y = ICON_Y + (i / 8) * 16;
            r.w = 4;
            r.h = 16;
            LoadImage(&r, (u_long*)s_SentPix[i]);
            for (k = 0; k < COLORS_PER_PAL; k++) {
                g_Clut[1][i * COLORS_PER_PAL + k + 0xD00] = s_SentPal[i][k];
            }
        }
    }
    LoadClut((u_long*)&g_Clut[1][0xD00], 0, ICON_PAL_Y);
    LoadClut((u_long*)&g_Clut[1][0xE00], 0, ICON_PAL_Y + 1);
}

void CoopLoadEquipIcon(s32 icon, s32 palette, s32 index) {
    if (s_Guest && !D_800973EC && (u32)index < ICON_SLOTS && (s_SentIcons & (1 << index)) && s_SentRoom == ROOM_NOW) {
        return; // the authority's icon is in that slot
    }
    ((void (*)(s32, s32, s32))s_IconTramp)(icon, palette, index);
}

// Each frame: this game is a room's guest, or isn't.
void VramGuest(bool guest) {
    static u8 s_Tick;

    s_Guest = guest;
    if (guest && ++s_Tick >= REAPPLY_EVERY) {
        s_Tick = 0;
        Reapply();
    }
}

// The guest's copy of what an upload put in an icon slot or the icons' palette rows.
static void KeepSent(const RECT* rect, const u16* p) {
    s32 i, k, slot;

    if (rect->w == 4 && rect->h == 16 && rect->x >= ICON_X && rect->x < ICON_X + 8 * 4 && !((rect->x - ICON_X) & 3) &&
        rect->y >= ICON_Y && rect->y < ICON_Y + 4 * 16 && !((rect->y - ICON_Y) & 15)) {
        slot = (rect->x - ICON_X) / 4 + (rect->y - ICON_Y) / 16 * 8;
        __builtin_memcpy(s_SentPix[slot], p, sizeof(s_SentPix[slot]));
        s_SentIcons |= 1 << slot;
        s_SentRoom = ROOM_NOW;
        return;
    }
    if (rect->x == 0 && rect->w == 0x100 && rect->h == 1 && (rect->y == ICON_PAL_Y || rect->y == ICON_PAL_Y + 1)) {
        for (i = 0; i < 16; i++) {
            slot = (rect->y - ICON_PAL_Y) * 16 + i;
            for (k = 0; k < COLORS_PER_PAL; k++) {
                s_SentPal[slot][k] = p[i * COLORS_PER_PAL + k];
            }
        }
    }
}

// A new room: the slots hold the last room's authority's icons, which DRA's record knows nothing of.
void VramForgetSent(void) {
    s32 i;

    if (s_SentRoom == ROOM_NOW) {
        return; // sent in this room (the arrival's first snapshot can come before it's counted)
    }
    for (i = 0; i < ICON_SLOTS; i++) {
        if (s_SentIcons & (1 << i)) {
            D_801374F8[i] = D_80137538[i] = NO_ICON;
        }
    }
    s_SentIcons = 0;
}

void VramPatch(void) {
    if (s_Patched) {
        return;
    }
    s_Patched = true;
    if (RESTORE_ICONS[0] == RESTORE_ICONS_FIRST) {
        RESTORE_ICONS[0] = J(CoopRestoreIcons);
        RESTORE_ICONS[1] = 0;
    }
    if (((u32*)LOAD_EQUIP_ICON)[0] == LOAD_EQUIP_ICON_FIRST) {
        s_IconTramp[0] = ((u32*)LOAD_EQUIP_ICON)[0];
        s_IconTramp[1] = ((u32*)LOAD_EQUIP_ICON)[1]; // sw s2, 40(sp): neither depends on where it runs
        s_IconTramp[2] = J(LOAD_EQUIP_ICON + 8);
        s_IconTramp[3] = 0;
        ((u32*)LOAD_EQUIP_ICON)[0] = J(CoopLoadEquipIcon);
        ((u32*)LOAD_EQUIP_ICON)[1] = 0;
    }
    if (LOAD_IMAGE[0] != LOAD_IMAGE_FIRST || LOAD_TPAGE[0] != LOAD_TPAGE_FIRST || LOAD_CLUT[0] != LOAD_CLUT_FIRST) {
        FlushCache();
        return; // not the code we expect: leave it all alone
    }
    LOAD_IMAGE[0] = J(CoopLoadImage);
    LOAD_IMAGE[1] = 0; // nop (delay slot)
    LOAD_TPAGE[0] = J(CoopLoadTPage);
    LOAD_TPAGE[1] = 0;
    LOAD_CLUT[0] = J(CoopLoadClut);
    LOAD_CLUT[1] = 0;
    FlushCache();
}

void VramRecord(bool on) {
    s32 i;

    s_Record = on;
    if (!on) {
        s_Size = 0;
        s_Resend = 0;
        return;
    }
    if (g_GameEngineStep != Engine_Normal) {
        return;
    }
    for (i = 0; i < ICON_SLOTS; i++) {
        if (D_801374F8[i] != NO_ICON) {
            s_Icons[i] = D_801374F8[i] + 1; // 0: nothing yet
            s_IconPals[i] = D_80137538[i];
            D_801374F8[i] = D_80137538[i] = NO_ICON;
        }
    }
    if (s_Resend > 0) { // one a frame (each brings its palette rows), every slot: what this game's
        i = --s_Resend;    // restore would put there, so the guest's restore keeps it all (#354)
        if (s_Icons[i]) {
            g_api.LoadEquipIcon(s_Icons[i] - 1, s_IconPals[i], i);
        } else {
            g_api.LoadEquipIcon(D_80137478[i], D_801374B8[i], i);
        }
    }
}

void VramResendIcons(void) { s_Resend = ICON_SLOTS; }

s32 VramTake(u8* out, s32 room) {
    s32 n = s_Size <= room ? s_Size : 0;

    if (n) {
        __builtin_memcpy(out, s_Uploads, n);
    }
    s_Size = 0;
    return n;
}

void VramApply(const u8* in, s32 size) {
    const u8* end = in + size;
    const RECT* rect;
    s32 bytes;

    while (in + sizeof(RECT) <= end) {
        rect = (const RECT*)in;
        bytes = (rect->w * rect->h * 2 + 3) & ~3;
        if (bytes <= 0 || in + sizeof(RECT) + bytes > end) {
            return;
        }
        GPU_QUEUE->addque2(GPU_QUEUE->dws, (void*)rect, sizeof(RECT), (void*)(in + sizeof(RECT)));
        KeepSent(rect, (const u16*)(in + sizeof(RECT)));
        in += sizeof(RECT) + bytes;
    }
}
