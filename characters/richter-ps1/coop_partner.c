// The partner's builds (coop_ric.h, COOP_PARTNER): their VRAM writes and reads, in VRAM's second
// bank (y bit 9: our SwanStation build, patches/swanstation.patch). A read from the bank still
// reads the first one: the core's VRAM-to-CPU copy doesn't know the bank yet (Richter's and
// Maria's death dissolve start from player 1's frame).
#include <game.h>
#undef LoadImage
#undef StoreImage
int LoadImage(RECT* rect, u_long* p);
int StoreImage(RECT* rect, u_long* p);

#define VRAM_BANK 0x200 // module/link.h

int CoopPartnerLoadImage(RECT* rect, u_long* p) {
    RECT r = *rect;
    r.y |= VRAM_BANK;
    return LoadImage(&r, p);
}

int CoopPartnerStoreImage(RECT* rect, u_long* p) {
    RECT r = *rect;
    r.y |= VRAM_BANK;
    return StoreImage(&r, p);
}
