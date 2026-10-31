; Stage 1: 512-byte boot sector. Loads the kernel with BIOS LBA reads,
; enters 32-bit protected mode, and jumps to the kernel at 0x1000.
[org 0x7c00]
[bits 16]

KERNEL_ADDR  equ 0x1000
KERNEL_SECTS equ 32              ; must cover the kernel image (see Makefile check)

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7c00
    sti
    mov [boot_drive], dl

    mov si, dap                  ; INT 13h extended read
    mov ah, 0x42
    mov dl, [boot_drive]
    int 0x13
    jc disk_error

    in al, 0x92                  ; fast A20
    or al, 2
    out 0x92, al

    cli
    lgdt [gdt_desc]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp 0x08:pm_entry

disk_error:
    mov si, err_msg
.l: lodsb
    test al, al
    jz .h
    mov ah, 0x0e
    int 0x10
    jmp .l
.h: hlt
    jmp .h

[bits 32]
pm_entry:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000
    jmp KERNEL_ADDR

[bits 16]
boot_drive: db 0
err_msg:    db "Disk error", 0

align 4
dap:
    db 0x10, 0
    dw KERNEL_SECTS
    dw KERNEL_ADDR, 0            ; offset, segment
    dq 1                         ; start LBA (sector after boot sector)

align 8
gdt:
    dq 0
    dq 0x00cf9a000000ffff        ; code
    dq 0x00cf92000000ffff        ; data
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

times 510 - ($ - $$) db 0
dw 0xaa55
