/* Our Richter as the partner (design/M13 step 3): the same objects as ric.ld, all linked in the
   8MB expansion RAM at PARTNER_RIC_ADDR (module/coop_api.h), so a second Richter runs beside
   player 1's with statics of its own. Data first (its g_PlOvl table and sprite table: the
   module swaps them into 0x8013C000 for the partner's frame), then the code, then the BSS,
   which the module zeroes. ric.ld's 'FAR1' trailer (farAddr is the code's address), then two
   more words: where each body's own data starts and its BSS ends (M17: the module swaps them per body). */
SECTIONS {
    . = 0x80740000;
    .data : {
        *(.data.RIC_player)
        *(.data.richter_sprites)
        *(.data.CoopRicBanks)
        /* M17: what never changes, shared by every body that runs this build... */
        *pl_header.o(.data*)
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
        *(COMMON)
        . = ALIGN(4);
        coop_shared_bss = .;  /* M17: the end of each body's own (the module swaps them per body) */
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
    }
    end = .;
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
