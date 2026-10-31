[bits 32]
[extern kmain]
global _start
_start:
    call kmain
.hang:
    cli
    hlt
    jmp .hang
