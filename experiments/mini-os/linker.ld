/*
 * linker.ld  —  Kernel linker script
 *
 * Places the kernel at physical address 0x1000 — exactly where the
 * bootloader loads it (INT 13h into ES:BX = 0000:1000).
 *
 * Output is a flat binary (--oformat binary passed to ld), so no ELF
 * headers are emitted — only raw machine code starting at 0x1000.
 */

ENTRY(kernel_main)

SECTIONS
{
    . = 0x1000;

    .text   : { *(.text.entry) *(.text*) }
    .rodata : { *(.rodata*) }
    .data   : { *(.data*)   }

    .bss : {
        __bss_start = .;
        *(.bss*)
        *(COMMON)
        __bss_end = .;
    }
}
