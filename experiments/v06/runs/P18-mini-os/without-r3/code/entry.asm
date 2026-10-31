[bits 32]
global _start
extern kmain
section .text.entry
_start:
    call kmain
.hang:
    cli
    hlt
    jmp .hang
