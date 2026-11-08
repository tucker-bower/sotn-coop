/* Ultimate Maria as the partner: ult_maria.ld's layout, all in the 8MB expansion RAM at
   PARTNER_MAR_ADDR (module/coop_api.h), as Co-op Maria's (characters/maria-dx/maria_partner.ld).
   The trailer's sixth word is her partner init (mar2.c CoopUltMarPartnerInit). */
EXTERN(MARIA_override);
SECTIONS {
    . = 0x80780000;
    .data : {
        *(.data.MARIA_override)
        *(.data.maria_sprites)
        *(.data.CoopMarBanks)
        *(.data.CoopMarHooks)
        *(.data.maria_pal)
        *(.data*)
        *(.rodata*)
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
        LONG(CoopUltMarPartnerInit)
    }
    end = .;
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
