; Boot sector: loads the kernel (KERNEL_SECTORS from LBA 1) to 0x1000,
; enables A20, enters 32-bit protected mode and jumps to the kernel.
BITS 16
ORG 0x7C00

KERNEL_SEG      equ 0x0100          ; 0x0100:0 = physical 0x1000
KERNEL_ADDR     equ 0x1000
KERNEL_SECTORS  equ 32

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
    mov ah, 0x42                    ; BIOS extended read
    mov dl, [boot_drive]
    int 0x13
    jc disk_error

    cli
    in al, 0x92                     ; fast A20
    or al, 2
    and al, 0xFE
    out 0x92, al

    lgdt [gdt_desc]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp 0x08:pm_entry

disk_error:
    mov si, err_msg
.next:
    lodsb
    test al, al
    jz .halt
    mov ah, 0x0E
    int 0x10
    jmp .next
.halt:
    hlt
    jmp .halt

BITS 32
pm_entry:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000
    jmp KERNEL_ADDR

BITS 16
boot_drive: db 0
err_msg:    db "Disk read error", 0

align 4
dap:
    db 0x10, 0
    dw KERNEL_SECTORS
    dw 0x0000, KERNEL_SEG           ; offset, segment
    dq 1                            ; starting LBA

align 8
gdt:
    dq 0
    dq 0x00CF9A000000FFFF           ; code: base 0, limit 4G, 32-bit
    dq 0x00CF92000000FFFF           ; data
gdt_end:
gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

times 510 - ($ - $$) db 0
dw 0xAA55
