[bits 32]
section .text.entry
global _start
extern kmain
_start:
    call kmain
.halt:
    cli
    hlt
    jmp .halt
