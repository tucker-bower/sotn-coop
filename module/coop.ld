/* Two outputs (Makefile): boot.bin, appended to DRA.BIN and run in place right behind DRA's
   image; and COOP.BIN, a disc file loaded into 8MB RAM by CoopBoot (boot.c). .bss is part of
   COOP.BIN: loading it is the only initialization. */
SECTIONS {
    .boot 0x801B9870 : {
        KEEP(*(.coop-boot))
        KEEP(*(.coop-boot-data))
    }
    .text 0x80280000 : {
        KEEP(*(.coop-table)) /* fixed addresses: dra_hooks.ld */
        *(.text*)
    }
    .data : {
        *(.rodata*)
        *(.data*)
        *(.sdata*)
        *(.bss*)
        *(.sbss*)
        *(COMMON)
        . = ALIGN(4);
    }
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) }
}
