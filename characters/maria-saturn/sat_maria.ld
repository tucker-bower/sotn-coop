/* Saturn Maria (Makefile): Co-op Richter's layout (characters/richter-ps1/ric.ld), her code at
   0x80640000 in the 8MB. */
SECTIONS {
    . = 0x8013C000;
    .data : {
        *(.data.RIC_player)
        *(.data.richter_sprites)
        
        *(.data*)
        *(.rodata*)
        *(.sdata*)
    }
    .text 0x80640000 : AT(LOADADDR(.data) + SIZEOF(.data)) {
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
