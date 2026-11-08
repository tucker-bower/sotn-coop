/* Ultimate Maria as player 1 (Makefile): Co-op Maria's layout (characters/maria-dx/maria.ld), so
   the module finds her at the same places. Data at Richter's overlay address, where DRA reads the
   player's table (0x8013C000) and sprites (0x8013C020); code and BSS in the 8MB expansion RAM, at
   an address of her own (0x80620000): code written over another character's at the same address
   can go unnoticed by an emulator's recompiler (module/coop_api.h COOP_PLAYER_FAR).
   The trailer's BSS is zeroed by the module, and mar2.c clears it too (mar2_bss_start). */
EXTERN(MARIA_override);
SECTIONS {
    . = 0x8013C000;
    .data : {
        *(.data.MARIA_override)
        *(.data.maria_sprites)
        *(.data.CoopMarBanks)    /* 0x8013C1F0: module/puppet.c reads her frame tables from here */
        *(.data.CoopMarHooks)    /* 0x8013C1F4: the module calls her guardians' graphics upload */
        *(.data.maria_pal)       /* 0x8013C1F8: ...and her palettes */
        *(.data.CoopUltMarHooks) /* 0x8013C7F8, after her palettes: her HUD icons (mar2.c CoopUltMarHud) */
        *(.data*)
        *(.rodata*)
        *(.sdata*)
    }
    .text 0x80620000 : AT(LOADADDR(.data) + SIZEOF(.data)) {
        *(.text*)
    }
    .bss (NOLOAD) : {
        mar2_bss_start = .;
        *(.bss*)
        *(.sbss*)
        *(.scommon)
        *(COMMON)
        . = ALIGN(4);
        mar2_bss_end = .;
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
