; Stage 1 bootloader: load kernel from disk, enter 32-bit protected mode.
[org 0x7c00]
[bits 16]
KERNEL_SEG equ 0x1000            ; kernel loaded at 0x10000
SECTORS    equ 17                ; sectors 2..18 of track 0 (fits one track)

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7c00
    sti
    mov [boot_drive], dl

    mov si, msg_load
    call print

    mov ax, KERNEL_SEG
    mov es, ax
    xor bx, bx
    mov ah, 0x02
    mov al, SECTORS
    mov ch, 0
    mov cl, 2
    mov dh, 0
    mov dl, [boot_drive]
    int 0x13
    jc disk_error

    cli
    lgdt [gdt_desc]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp 0x08:pm_entry

disk_error:
    mov si, msg_err
    call print
    jmp $

print:
    lodsb
    test al, al
    jz .done
    mov ah, 0x0e
    int 0x10
    jmp print
.done:
    ret

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
gdt:
    dq 0
    dq 0x00cf9a000000ffff        ; code
    dq 0x00cf92000000ffff        ; data
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

boot_drive db 0
msg_load db "Loading kernel...", 13, 10, 0
msg_err  db "Disk error", 0

times 510-($-$$) db 0
dw 0xaa55
