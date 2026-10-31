# MiniOS

Minimal x86 BIOS OS: NASM boot sector (`os/boot.asm`) loads a freestanding C kernel (`os/kernel.c`)
into memory, switches to 32-bit protected mode and prints text via VGA text memory (0xB8000).
No external libraries.

    make        # builds os/build/os.img
    make run    # boots it in QEMU (qemu-system-i386)
    make clean

Requires `nasm`, `i686-elf-gcc`/`i686-elf-ld`/`i686-elf-objcopy` and `qemu-system-i386`.
