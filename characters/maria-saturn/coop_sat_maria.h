// Saturn Maria's partner build (Makefile: -include, with COOP_PARTNER): a second Saturn Maria
// beside player 1. Her VRAM writes and reads go to the second bank (characters/richter-ps1/
// coop_partner.c), and her palettes to a g_Clut of her own, never player 1's.
#ifndef COOP_SAT_MARIA_H
#define COOP_SAT_MARIA_H

#ifdef COOP_PARTNER
#define LoadImage CoopPartnerLoadImage
#define StoreImage CoopPartnerStoreImage
#define g_Clut g_CoopPartnerClut
#endif

#endif
