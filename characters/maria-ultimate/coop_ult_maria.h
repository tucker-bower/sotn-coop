// Ultimate Maria's link to co-op (docs/design/character-mods.md): included in every file of her
// build (Makefile: -include). Her sources are upstream's src/maria with none of Co-op Maria's
// changes (no COOP_MARIA), and mar2.c, SOTN Ultimate's glue.
#ifndef COOP_ULT_MARIA_H
#define COOP_ULT_MARIA_H

// SOTN Ultimate's flags byte (its mods/sotn-ultimate/include/game_mod.h): a spare byte of the
// save name. Co-op uses nothing there. Only her two-slot flag is used here.
#define MOD_STATUS_FLAGS g_Status.saveName[11]
#define MOD_FLAG_MARIA_SUB2 0x10

// The partner's build (COOP_PARTNER): her VRAM writes and reads go to the second bank
// (characters/richter-ps1/coop_partner.c), and her palettes to a g_Clut of her own (mar2.c).
#ifdef COOP_PARTNER
#define LoadImage CoopPartnerLoadImage
#define StoreImage CoopPartnerStoreImage
#define g_Clut g_CoopPartnerClut
#endif

#endif
