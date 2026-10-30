/* Our Richter as the partner (design/M13 step 3): the same objects as ric.ld, all linked in the
   8MB expansion RAM at PARTNER_RIC_ADDR (module/coop_api.h), so a second Richter runs beside
   player 1's with statics of its own. Data first (its g_PlOvl table and sprite table: the
   module swaps them into 0x8013C000 for the partner's frame), then the code, then the BSS,
   which the module zeroes. The same 'FAR1' trailer as ric.ld: farAddr is the code's address. */
SECTIONS {
    . = 0x80740000;
    .data : {
        *(.data.RIC_player)
        *(.data.richter_sprites)
        *(.data.CoopRicBanks)
        *(.data*)
        *(.rodata*)
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
    }
    .trailer : AT(LOADADDR(.text) + SIZEOF(.text)) {
        LONG(0x31524146)  /* 'FAR1' */
        LONG(SIZEOF(.data))
        LONG(SIZEOF(.text))
        LONG(SIZEOF(.bss))
        LONG(ADDR(.text))
    }
    end = .;
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
