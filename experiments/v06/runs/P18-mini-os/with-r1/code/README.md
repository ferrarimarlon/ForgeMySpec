# Mini OS

Minimal x86 bare-metal OS: a 512-byte boot sector (real mode → A20 → GDT → 32-bit protected mode) and a freestanding C kernel that writes to VGA text memory at 0xB8000. No external libraries.

- `make` builds `build/os.img` (needs `nasm`, `i686-elf-gcc`/`ld`/`objcopy`)
- `make run` boots it in QEMU (`qemu-system-i386`)
- `python3 -m unittest discover tests` runs the checks, including a headless QEMU boot

Layout: `boot/boot.asm`, `kernel/entry.asm`, `kernel/kernel.c`, `kernel/linker.ld`. The kernel is limited to 8 KiB (16 sectors loaded by the boot sector).
