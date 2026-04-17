# Implement Mini OS from Spec

Execute this command to implement the Mini OS from `spec.yaml`.

## Steps

1. **Read the spec** — open `spec.yaml` and internalize objective, constraints, success_criteria, and required_evidence.

2. **Action a1 — Layout**
   Create directory structure:
   ```
   examples/mini-os/
   ├── boot/boot.asm
   ├── kernel/kernel.c
   ├── linker.ld
   └── Makefile
   ```

3. **Action a2 — Bootloader** (`boot/boot.asm`)
   - 16-bit ORG 0x7C00 entry
   - Zero segment registers, set stack to 0x7C00
   - BIOS INT 13h / AH=02h: read 32 sectors from sector 2 into 0x0000:0x1000
   - Enable A20 via port 0x92
   - Define GDT: null + code(0x08) + data(0x10), 32-bit flat
   - `lgdt`, set CR0 bit 0, far jump to `CODE_SEG:protected_mode`
   - 32-bit stub: set data segments, `mov esp, 0x90000`, `call 0x1000`
   - `times 510-($ - $$) db 0` + `dw 0xAA55`

4. **Action a3 — Kernel** (`kernel/kernel.c`)
   - `#define VGA_BASE 0xB8000`, `VGA_COLS 80`, `VGA_ROWS 25`
   - Helpers: `vga_clear`, `vga_scroll`, `vga_putchar(char, attr)`, `print`, `print_uint`, `print_hex`, `hline`
   - `kernel_main`: clear, banner, boot addresses, memory map, GDT selectors, footer, `cli; hlt` loop

5. **Action a4 — Linker script** (`linker.ld`)
   - `ENTRY(kernel_main)`, `. = 0x1000`
   - Sections: `.text`, `.rodata`, `.data`, `.bss`

6. **Action a5 — Makefile**
   ```makefile
   BUILD = build
   all:  $(BUILD)/os.img
   boot: nasm -f bin -o $(BUILD)/boot.bin boot/boot.asm
   kernel: gcc -m32 -ffreestanding -fno-pie -nostdlib -nostdinc -O2 -c ...
            ld -m elf_i386 --oformat binary -T linker.ld -o $(BUILD)/kernel.bin ...
   image: cat boot.bin kernel.bin > os.img && truncate -s 32768 os.img
   run:  qemu-system-x86_64 -drive format=raw,file=$(BUILD)/os.img -nographic
   clean: rm -rf $(BUILD)
   ```

7. **Action a6 — Validate**
   - Run `make` → confirm exit 0 and `build/os.img` created
   - Run `wc -c build/boot.bin` → must be 512
   - Run `make run` → confirm QEMU banner visible
   - Run `make clean` → confirm artefacts removed

8. **Complete acceptance-checklist.md** — check every box honestly.

## Constraints reminder
- No libc, no crt0, no external libraries.
- All files inside `examples/mini-os/`.
- Do not implement filesystem, interrupts, keyboard, or scheduler.
