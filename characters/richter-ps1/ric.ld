/* Our Richter (Makefile): linked at Richter's overlay address. pl_header's .data comes first
   (the g_PlOvl table DRA jumps through), then richter_sprites: DRA reads Richter's sprite
   table at a fixed address (g_PlOvlSpritesheet, 0x8013C020), and the puppet code finds his
   frame tables right after it.
   Only the data stays in Richter's slot (0x8013C000): the code and BSS run from the 8MB
   expansion RAM (0x805C0000; Maria's at 0x80600000: each address only ever holds one
   character's code, since emulators' recompilers may not notice code rewritten there). So the slot ends below 0x80170000,
   where familiars load (design/M8b §3: familiars for Richter and Maria too). The file is the
   slot's part, then the code (put at the far address by the module, which also zeroes the BSS:
   module/character.c), then a 20-byte trailer: 'FAR1', the slot part's size, the code's size, the BSS's size, the code's
   address. */
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
    .text 0x805C0000 : AT(LOADADDR(.data) + SIZEOF(.data)) {
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
