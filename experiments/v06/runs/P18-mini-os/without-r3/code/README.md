# MiniOS

Tiny x86 OS: 512-byte boot sector (real mode -> protected mode) + C kernel with VGA text output, PS/2 keyboard and a small shell. No external libraries.

Requires `nasm`, `i686-elf-gcc`/`i686-elf-ld`, `qemu-system-i386`.

    make        # builds os.img
    make run    # boots in QEMU

Shell commands: `help clear mem color ticks halt`.
Layout: `boot.asm` (loads 32 sectors to 0x1000 via INT 13h LBA), `entry.asm`, `kernel.c`, `link.ld`.
