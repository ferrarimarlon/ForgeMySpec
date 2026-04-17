; entry.asm  —  Kernel entry point
;
; Linked first (section .text.entry) so it sits at the binary's byte 0.
; The bootloader does "call 0x1000" which lands here.
;
; Build:  nasm -f elf32 -o build/entry.o kernel/entry.asm

[BITS 32]

extern kernel_main

section .text.entry
global _start
_start:
    call kernel_main
    cli
.hang:
    hlt
    jmp .hang
