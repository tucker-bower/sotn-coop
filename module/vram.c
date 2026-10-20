// VRAM uploads for a shared room's guest (playtest 2 prep: a relic's "Obtained ..." box was empty
// on the guest's screen).
//
// Some stage entities write into VRAM as they run: the text of an item's or relic's message
// box, palette fades. The guest doesn't run them, so it gets their primitives (from the
// snapshot) but not the picture they show. The module patches libgpu's LoadImage (main.exe,
// always resident) to come here; uploads made by the stage overlay's code while this game is a
// room's authority are recorded and sent with the snapshot, and the guest makes them too.
// Uploads from DRA (the player's sprite frames, every frame) are each game's own and never sent.
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

static bool StageCaller(u32 caller) {
    const OverlayInfo* ovl;

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

void VramPatch(void) {
    if (s_Patched) {
        return;
    }
    s_Patched = true;
    if (LOAD_IMAGE[0] != LOAD_IMAGE_FIRST || LOAD_TPAGE[0] != LOAD_TPAGE_FIRST || LOAD_CLUT[0] != LOAD_CLUT_FIRST) {
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
    s_Record = on;
    if (!on) {
        s_Size = 0;
    }
}

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
        in += sizeof(RECT) + bytes;
    }
}
