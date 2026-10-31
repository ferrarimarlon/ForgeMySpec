; Stage 1 bootloader: loads the kernel with BIOS LBA reads, enters 32-bit
; protected mode and jumps to the kernel. KERNEL_SECTORS is set by the Makefile.
[bits 16]
[org 0x7c00]

KERNEL_SEG equ 0x1000            ; kernel loaded at physical 0x10000

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7c00
    sti
    mov [boot_drive], dl

    mov si, dap
    mov ah, 0x42
    mov dl, [boot_drive]
    int 0x13
    jc disk_error

    in al, 0x92                  ; enable A20 (fast gate)
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
.loop:
    lodsb
    test al, al
    jz .halt
    mov ah, 0x0e
    int 0x10
    jmp .loop
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
    jmp 0x08:0x10000

[bits 16]
err_msg db "Disk read error", 0
boot_drive db 0

align 4
dap:
    db 0x10, 0
    dw KERNEL_SECTORS
    dw 0x0000, KERNEL_SEG
    dq 1

gdt:
    dq 0
    dq 0x00cf9a000000ffff        ; code: base 0, limit 4G, 32-bit
    dq 0x00cf92000000ffff        ; data
gdt_desc:
    dw gdt_desc - gdt - 1
    dd gdt

times 510 - ($ - $$) db 0
dw 0xaa55
