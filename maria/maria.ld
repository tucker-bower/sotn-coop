/* Our Maria (Makefile): linked at Richter's overlay address, where she runs. MARIA_override
   (the g_PlOvl table DRA jumps through) comes first, then maria_sprites: DRA reads the player's
   sprite table at a fixed address (0x8013C020). .bss is in the file, zeroed: the game's CD
   loader doesn't clear it, and leftovers there kept her init from running. */
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
    .text : {
        *(.text*)
    }
    .bss : {
        *(.bss*)
        *(.sbss*)
        *(.scommon)
        *(COMMON)
        . = ALIGN(4);
        LONG(0)
    }
    end = .;
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
