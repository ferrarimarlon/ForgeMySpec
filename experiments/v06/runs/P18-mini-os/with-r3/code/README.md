# MiniOS
Minimal x86 OS: 512-byte BIOS boot sector -> protected mode -> freestanding C kernel printing via VGA text memory (0xB8000).
Needs `nasm`, `i686-elf-gcc`/`ld`/`objcopy`, `qemu-system-i386`. `make` builds `build/os.img`; `make run` boots it in QEMU.
