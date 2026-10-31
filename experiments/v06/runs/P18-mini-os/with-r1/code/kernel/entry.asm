; Kernel entry point, reached from the boot sector in 32-bit protected mode.
bits 32
section .text.entry
global _start
extern kmain

_start:
    call kmain
.hang:
    cli
    hlt
    jmp .hang
