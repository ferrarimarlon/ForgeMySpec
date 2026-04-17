; =============================================================================
; boot.asm  —  512-byte x86 BIOS bootloader
;
; Flow:
;   1. 16-bit real-mode init (segments, stack)
;   2. Load kernel sectors from disk via BIOS INT 13h
;   3. Enable A20 line (fast-A20 via port 0x92)
;   4. Define GDT (null / code / data)
;   5. Switch to 32-bit protected mode
;   6. Jump to kernel at physical address 0x1000
;
; Build:  nasm -f bin -o build/boot.bin boot/boot.asm
; =============================================================================

[BITS 16]
[ORG 0x7C00]

; ── 16-bit entry ─────────────────────────────────────────────────────────────
start:
    cli
    xor  ax, ax
    mov  ds, ax
    mov  es, ax
    mov  ss, ax
    mov  sp, 0x7C00          ; stack grows down from load address

    ; ── Load kernel from disk (BIOS INT 13h / AH=02h) ──────────────────────
    mov  ah, 0x02            ; read sectors
    mov  al, 32              ; 32 sectors × 512 B = 16 KiB
    mov  ch, 0               ; cylinder 0
    mov  cl, 2               ; start at sector 2 (sector 1 = this MBR)
    mov  dh, 0               ; head 0
    xor  bx, bx
    mov  es, bx
    mov  bx, 0x1000          ; ES:BX = 0000:1000 → physical 0x1000
    int  0x13
    jc   .disk_err

    ; ── Enable A20 (fast-A20 via port 0x92) ────────────────────────────────
    in   al, 0x92
    or   al, 0x02
    and  al, 0xFE
    out  0x92, al

    ; ── Load GDT, enter protected mode ─────────────────────────────────────
    cli
    lgdt [gdt_desc]

    mov  eax, cr0
    or   eax, 1
    mov  cr0, eax

    jmp  CODE_SEG:pm_entry   ; far jump flushes pipeline / loads CS

; ── Disk error handler (print message, halt) ─────────────────────────────────
.disk_err:
    mov  si, msg_err
.print:
    lodsb
    test al, al
    jz   .halt
    mov  ah, 0x0E
    int  0x10
    jmp  .print
.halt:
    hlt
    jmp  .halt

msg_err db 'Disk error', 0

; ── GDT ──────────────────────────────────────────────────────────────────────
align 4
gdt_start:
    dq 0                     ; 0x00  null descriptor
gdt_code:                    ; 0x08  ring-0 32-bit code, base=0, limit=4G
    dw 0xFFFF                ;   limit[15:0]
    dw 0x0000                ;   base[15:0]
    db 0x00                  ;   base[23:16]
    db 10011010b             ;   P DPL=0 S type=code/read
    db 11001111b             ;   G=1 D/B=1 limit[19:16]=F
    db 0x00                  ;   base[31:24]
gdt_data:                    ; 0x10  ring-0 32-bit data
    dw 0xFFFF
    dw 0x0000
    db 0x00
    db 10010010b             ;   P DPL=0 S type=data/write
    db 11001111b
    db 0x00
gdt_end:

gdt_desc:
    dw gdt_end - gdt_start - 1
    dd gdt_start

CODE_SEG equ gdt_code - gdt_start   ; 0x08
DATA_SEG equ gdt_data - gdt_start   ; 0x10

; ── 32-bit protected-mode stub ────────────────────────────────────────────────
[BITS 32]
pm_entry:
    mov  ax, DATA_SEG
    mov  ds, ax
    mov  es, ax
    mov  fs, ax
    mov  gs, ax
    mov  ss, ax
    mov  esp, 0x90000        ; stack at 576 KiB (below 640 KiB boundary)

    call 0x1000              ; jump to kernel_main

    ; should never return
    cli
.hang:
    hlt
    jmp  .hang

; ── Boot sector padding + magic ───────────────────────────────────────────────
times 510 - ($ - $$) db 0
dw 0xAA55
