; Boot sector: loads the kernel with BIOS int 13h (LBA), enters protected mode.
%ifndef KSECTORS
%define KSECTORS 32
%endif
KERNEL_ADDR equ 0x1000

[bits 16]
[org 0x7C00]
start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    sti
    mov [boot_drive], dl

    mov si, dap
    mov ah, 0x42
    mov dl, [boot_drive]
    int 0x13
    jc disk_error

    cli
    lgdt [gdt_desc]
    mov eax, cr0
    or eax, 1                  ; CR0.PE: enter protected mode
    mov cr0, eax
    jmp 0x08:pm_entry

disk_error:
    mov si, msg_err
.print:
    lodsb
    test al, al
    jz .halt
    mov ah, 0x0E
    int 0x10
    jmp .print
.halt:
    hlt
    jmp .halt

[bits 32]
pm_entry:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000
    jmp 0x08:KERNEL_ADDR

[bits 16]
msg_err db "Disk error", 0
boot_drive db 0

align 4
dap:
    db 0x10, 0
    dw KSECTORS
    dw KERNEL_ADDR, 0
    dq 1

align 8
gdt:
    dq 0
    dq 0x00CF9A000000FFFF      ; code, 4 GiB flat
    dq 0x00CF92000000FFFF      ; data, 4 GiB flat
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

times 510 - ($ - $$) db 0
dw 0xAA55
