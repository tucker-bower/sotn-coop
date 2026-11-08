/* Saturn Maria as the partner: sat_maria.ld's layout, all in the 8MB at PARTNER_SAT_ADDR
   (module/coop_api.h), as Co-op Richter's partner (characters/richter-ps1/ric_partner.ld). */
SECTIONS {
    . = 0x80200000;
    .data : {
        *(.data.RIC_player)
        *(.data.richter_sprites)
        
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
