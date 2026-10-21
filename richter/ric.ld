/* Our Richter (Makefile): linked at Richter's overlay address. pl_header's .data comes first
   (the g_PlOvl table DRA jumps through), then richter_sprites: DRA reads Richter's sprite
   table at a fixed address (g_PlOvlSpritesheet, 0x8013C020), and the puppet code finds his
   frame tables right after it. .bss is in the file, zeroed, as in COOP.BIN: the
   game's CD loader doesn't clear it, so loading the file is its only initialization. */
SECTIONS {
    . = 0x8013C000;
    .data : {
        *(.data.RIC_player)
        *(.data.richter_sprites)
        *(.data.CoopRicBanks)  /* 0x8013C334: module/puppet.c reads it from its copy */
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
