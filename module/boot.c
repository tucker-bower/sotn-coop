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
#define BOOT_HELPER __attribute__((section(".coop-boot-helpers"))) // after CoopBoot (coop.ld)

// String literals would land in .rodata, which is in COOP.BIN: keep this one here.
static char s_CoopFile[] __attribute__((section(".coop-boot-data"))) = "\\COOP.BIN;1";
static char s_RicFile[] __attribute__((section(".coop-boot-data"))) = "\\COOPRIC.BIN;1";
static char s_AluFile[] __attribute__((section(".coop-boot-data"))) = "\\BIN\\ARC_F.BIN;1";
static char s_RicHudFile[] __attribute__((section(".coop-boot-data"))) = "\\BIN\\F_GAME2.BIN;1";
static char s_RicPartnerFile[] __attribute__((section(".coop-boot-data"))) = "\\COOPRICP.BIN;1";

// Reads a disc file, or `sectors` of it from sector `skip` (0: all of it), to dst. file gets its
// CdlFILE (size 0: not on the disc). retry: until it's found (COOP.BIN must be there).
static void BOOT_HELPER ReadFile(char* name, void* dst, CdlFILE* file, bool retry, s32 skip, s32 sectors) {
    u8 mode = CdlModeSpeed;
    CdlLOC pos;

    file->size = 0;
    do {
        while (!CdSearchFile(file, name)) {
            if (!retry) {
                file->size = 0;
                return;
            }
        }
        CdIntToPos(CdPosToInt(&file->pos) + skip, &pos);
        CdControl(CdlSetmode, &mode, NULL);
        CdControl(CdlSetloc, (u8*)&pos, NULL);
        CdRead(sectors ? sectors : (file->size + 0x7FF) >> 11, (u_long*)dst, CdlModeSpeed);
    } while (CdReadSync(0, NULL) < 0);
}

void BOOT CoopBoot(void) {
    CdlFILE file;

    *(volatile u32*)0x1F801060 |= 0xE00; // RAM_SIZE: expose 8MB
    ReadFile(s_CoopFile, (void*)COOP_ADDR, &file, true, 0, 0);
    // Our Richter (design/M8): character.c points Richter's CD load at it, and a copy stays in
    // 8MB RAM with Alucard's sprites, to draw a partner who plays another character (puppet.c).
    // Now is the only safe time to read them: in play, the CD streams the music.
    ReadFile(s_RicFile, (void*)PUPPET_RIC_ADDR, &g_CoopRicFile, false, 0, 0);
    ReadFile(s_AluFile, (void*)PUPPET_ALU_ADDR, &file, false, 0, 0);
    // Richter's graphics file (his palettes 0x100-0x13F are at 0x40000 in it), for the puppet,
    // and for a Richter partner's own graphics in VRAM's second bank (design/M13 step 3)...
    ReadFile(s_RicHudFile, (void*)FGAME2_ADDR, &file, false, 0, 0);
    // ...and the partner's Richter, linked to run there (richter/ric_partner.ld).
    ReadFile(s_RicPartnerFile, (void*)PARTNER_RIC_ADDR, &g_CoopRicPartnerFile, false, 0, 0);
    FlushCache(); // just loaded code: the I-cache and recompilers only see it after a flush (D17)
    InitializePads();
}
