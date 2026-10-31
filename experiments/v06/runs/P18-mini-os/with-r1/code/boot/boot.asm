; Mini OS boot sector: BIOS loads us at 0x7C00 in 16-bit real mode.
; Loads the kernel from disk, enables A20, switches to 32-bit protected
; mode with a flat GDT and jumps to the kernel entry point.
bits 16
org 0x7C00

KERNEL_ADDR    equ 0x1000
KERNEL_SECTORS equ 16              ; sectors 2..17 of track 0 (8 KiB max)

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    sti
    mov [boot_drive], dl           ; BIOS passes the boot drive in DL

    mov ah, 0x02                   ; int 13h: read sectors (CHS)
    mov al, KERNEL_SECTORS
    mov ch, 0                      ; cylinder 0
    mov cl, 2                      ; first sector after the boot sector
    mov dh, 0                      ; head 0
    mov dl, [boot_drive]
    mov bx, KERNEL_ADDR
    int 0x13
    jc disk_error

    in al, 0x92                    ; enable A20 via fast gate
    or al, 2
    out 0x92, al

    cli
    lgdt [gdt_descriptor]
    mov eax, cr0
    or eax, 1                      ; CR0.PE = protected mode
    mov cr0, eax
    jmp CODE_SEG:protected_mode    ; far jump flushes the pipeline, loads CS

disk_error:
    mov si, err_msg
.next:
    lodsb
    test al, al
    jz .halt
    mov ah, 0x0E                   ; BIOS teletype
    int 0x10
    jmp .next
.halt:
    hlt
    jmp .halt

bits 32
protected_mode:
    mov ax, DATA_SEG
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x90000
    jmp KERNEL_ADDR                ; entry point of the kernel

bits 16
align 8
gdt_start:
    dq 0                           ; null descriptor
gdt_code:
    dw 0xFFFF, 0x0000
    db 0x00, 10011010b, 11001111b, 0x00   ; base 0, limit 4 GiB, ring 0 code
gdt_data:
    dw 0xFFFF, 0x0000
    db 0x00, 10010010b, 11001111b, 0x00   ; base 0, limit 4 GiB, ring 0 data
gdt_end:

gdt_descriptor:
    dw gdt_end - gdt_start - 1
    dd gdt_start

CODE_SEG equ gdt_code - gdt_start
DATA_SEG equ gdt_data - gdt_start

boot_drive: db 0
err_msg:    db "Disk read error", 0

times 510 - ($ - $$) db 0
dw 0xAA55
