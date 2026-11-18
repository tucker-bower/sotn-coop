/* Our Maria as the partner (design/M13 step 3): maria.ld's layout, all in the 8MB expansion RAM at
   PARTNER_MAR_ADDR (module/coop_api.h), with statics of her own; the trailer's sixth word is her
   partner init (coop_maria.c's CoopMarPartnerInit).
   From maria.ld: linked at Richter's overlay address, where she runs. MARIA_override
   (the g_PlOvl table DRA jumps through) comes first, then maria_sprites: DRA reads the player's
   sprite table at a fixed address (0x8013C020). Her code and BSS run from the 8MB expansion RAM,
   as our Richter's do (characters/richter-ps1/ric.ld): the module zeroes the BSS (leftovers there kept her
   init from running). */
SECTIONS {
    . = 0x80780000;
    .data : {
        *(.data.MARIA_override)
        *(.data.maria_sprites)
        *(.data.CoopMarBanks)  /* 0x8013C1F0: module/puppet.c reads her frame tables from here */
        *(.data.CoopMarHooks)  /* 0x8013C1F4: the module calls her guardians' graphics upload */
        *(.data.maria_pal)     /* 0x8013C1F8: ...and her palettes */
        /* M17: what never changes, shared by every body that runs this build... */
        *maria.o(.data*)
        *ovl_load.o(.data*)
        *spritebanks.o(.data*)
        *(.rodata*)
        . = ALIGN(4);
        coop_statics = .;  /* ...then each body's own (the module swaps them per body) */
        *(.data*)
        *(.sdata*)
    }
    .text : {
        *(.text*)
    }
    .bss (NOLOAD) : {
        *(.bss*)
        *(.sbss*)
        *(.scommon)
        *(EXCLUDE_FILE(*coop_maria.o) COMMON)
        . = ALIGN(4);
        coop_shared_bss = .;  /* M17: kept by every body: her palettes' copy (g_CoopPartnerClut) */
        *(COMMON)
        . = ALIGN(4);
    }
    ASSERT((ADDR(.text) - coop_statics) + (coop_shared_bss - ADDR(.bss)) <= 0x5000,
           "each body's statics outgrow the module's buffer for them (module/partner.c STATICS_MAX)")
    .trailer : AT(LOADADDR(.text) + SIZEOF(.text)) {
        LONG(0x31524146)  /* 'FAR1' */
        LONG(SIZEOF(.data))
        LONG(SIZEOF(.text))
        LONG(SIZEOF(.bss))
        LONG(ADDR(.text))
        LONG(coop_statics)     /* M17: each body's own data, from here to the code */
        LONG(coop_shared_bss)  /* ...and BSS, from its start to here */
        LONG(CoopMarPartnerInit)
    }
    end = .;
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
