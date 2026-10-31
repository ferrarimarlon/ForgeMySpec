# MiniOS
Tiny x86 OS: 512-byte boot sector (BIOS LBA load, A20, protected mode) + C kernel with VGA text console and polled keyboard shell.

Requires nasm, i686-elf-gcc/ld, qemu. `make run` to boot; shell commands: help clear about color reboot halt.
