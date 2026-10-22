/* Our Maria (Makefile): linked at Richter's overlay address, where she runs. MARIA_override
   (the g_PlOvl table DRA jumps through) comes first, then maria_sprites: DRA reads the player's
   sprite table at a fixed address (0x8013C020). Her code and BSS run from the 8MB expansion RAM,
   as our Richter's do (richter/ric.ld): the module zeroes the BSS (leftovers there kept her
   init from running). */
SECTIONS {
    . = 0x8013C000;
    .data : {
        *(.data.MARIA_override)
        *(.data.maria_sprites)
        *(.data.CoopMarBanks)  /* 0x8013C1F0: module/puppet.c reads her frame tables from here */
        *(.data.maria_pal)     /* 0x8013C1F4: ...and her palettes */
        *(.data*)
        *(.rodata*)
        *(.sdata*)
    }
    .text 0x80600000 : AT(LOADADDR(.data) + SIZEOF(.data)) {
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
