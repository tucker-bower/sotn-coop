// The partner's builds (coop_ric.h, COOP_PARTNER): their VRAM writes and reads, in the body's VRAM
// bank (y bits 9-10: our SwanStation build, patches/swanstation.patch; M17: the module says which,
// in g_CoopPartnerVram, for each body's frame). A read from the bank still
// reads the first one: the core's VRAM-to-CPU copy doesn't know the bank yet (Richter's and
// Maria's death dissolve start from player 1's frame).
#include <game.h>
#undef LoadImage
#undef StoreImage
int LoadImage(RECT* rect, u_long* p);
int StoreImage(RECT* rect, u_long* p);

extern u32 g_CoopPartnerVram; // the module's fixed table (coop_player.ld): VRAM_BANK_OF(the body's bank)

int CoopPartnerLoadImage(RECT* rect, u_long* p) {
    RECT r = *rect;
    r.y |= g_CoopPartnerVram;
    return LoadImage(&r, p);
}

int CoopPartnerStoreImage(RECT* rect, u_long* p) {
    RECT r = *rect;
    r.y |= g_CoopPartnerVram;
    return StoreImage(&r, p);
}
