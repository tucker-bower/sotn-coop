// CoopBoot: the only co-op code in DRA.BIN. It's appended to DRA's image and runs in place
// (0x801B9870) as the first call in MainGame, before anything can overwrite it. It loads
// COOP.BIN (the rest of the module) from the disc into 8MB RAM, the way main.exe loads DRA.BIN.
//
// It has to fit in the unused tail of DRA.BIN's last CD sector: growing DRA.BIN by a sector
// would shift every later file on the disc, and the FMVs are played from fixed positions.
#define COOP_MODULE
#include <game.h>
#include <psxsdk/libcd.h>
#include "coop_api.h"

void InitializePads(void); // DRA
void FlushCache(void);     // main.exe (PsyQ)

#define BOOT __attribute__((section(".coop-boot")))

// String literals would land in .rodata, which is in COOP.BIN: keep this one here.
static char s_CoopFile[] __attribute__((section(".coop-boot-data"))) = "\\COOP.BIN;1";

void BOOT CoopBoot(void) {
    CdlFILE file;
    u8 mode = CdlModeSpeed;

    *(volatile u32*)0x1F801060 |= 0xE00; // RAM_SIZE: expose 8MB
    do {
        while (!CdSearchFile(&file, s_CoopFile)) {
        }
        CdControl(CdlSetmode, &mode, NULL);
        CdControl(CdlSetloc, (u8*)&file.pos, NULL);
        CdRead((file.size + 0x7FF) >> 11, (u_long*)COOP_ADDR, CdlModeSpeed);
    } while (CdReadSync(0, NULL) < 0);
    FlushCache(); // just loaded code: the I-cache and recompilers only see it after a flush (D17)
    InitializePads();
}
