/* Saturn Maria as the partner: sat_maria.ld's layout, all in the 8MB at PARTNER_SAT_ADDR
   (module/coop_api.h), as Co-op Richter's partner (characters/richter-ps1/ric_partner.ld). */
SECTIONS {
    . = 0x80200000;
    .data : {
        *(.data.RIC_player)
        *(.data.richter_sprites)
        
        /* M17: what never changes, shared by every body that runs this build... */
        *pl_header.o(.data*)
        *pl_blueprints.o(.data*)
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
        *(EXCLUDE_FILE(*coop_sat_partner.o) COMMON)
        . = ALIGN(4);
        coop_shared_bss = .;  /* M17: kept by every body: her palettes' copy (g_CoopPartnerClut) */
        *(COMMON)
        . = ALIGN(4);
    }
    ASSERT((ADDR(.text) - coop_statics) + (coop_shared_bss - ADDR(.bss)) + 0x588 <= 0x5000,
           "each body's statics outgrow the module's buffer for them (module/partner.c STATICS_MAX)")
    .trailer : AT(LOADADDR(.text) + SIZEOF(.text)) {
        LONG(0x31524146)  /* 'FAR1' */
        LONG(SIZEOF(.data))
        LONG(SIZEOF(.text))
        LONG(SIZEOF(.bss))
        LONG(ADDR(.text))
        LONG(coop_statics)     /* M17: each body's own data, from here to the code */
        LONG(coop_shared_bss)  /* ...and BSS, from its start to here */
    }
    end = .;
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
