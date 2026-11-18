/* Ultimate Maria as the partner: ult_maria.ld's layout, all in the 8MB expansion RAM at
   PARTNER_ULT_ADDR (module/coop_api.h), apart from Co-op Maria's: a partner who switches from one to
   the other would otherwise run new code where the recompiler kept the old (it hung).
   The trailer's sixth word is her partner init (mar2.c CoopUltMarPartnerInit). */
EXTERN(MARIA_override);
SECTIONS {
    . = 0x804C0000;
    .data : {
        *(.data.MARIA_override)
        *(.data.maria_sprites)
        *(.data.CoopMarBanks)
        *(.data.CoopMarHooks)
        *(.data.maria_pal)
        /* M17: what never changes, shared by every body that runs this build... */
        *mar2.o(.data.maria_*)  /* her sprites' frames (mar2.c's own data is each body's) */
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
        mar2_bss_start = .;
        *(.bss*)
        *(.sbss*)
        *(.scommon)
        *(EXCLUDE_FILE(*mar2.o) COMMON)
        . = ALIGN(4);
        coop_shared_bss = .;  /* M17: kept by every body: her palettes' copy (g_CoopPartnerClut) */
        *(COMMON)
        . = ALIGN(4);
        mar2_bss_end = .;
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
        LONG(CoopUltMarPartnerInit)
    }
    end = .;
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
