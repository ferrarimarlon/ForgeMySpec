CC = i686-elf-gcc
LD = i686-elf-ld
CFLAGS = -m32 -ffreestanding -fno-pic -fno-stack-protector -O2 -Wall -Wextra -nostdlib

all: os.img

boot.bin: boot.asm
	nasm -f bin $< -o $@

entry.o: entry.asm
	nasm -f elf32 $< -o $@

kernel.o: kernel.c
	$(CC) $(CFLAGS) -c $< -o $@

kernel.bin: entry.o kernel.o link.ld
	$(LD) -m elf_i386 -T link.ld --oformat binary entry.o kernel.o -o $@
	@test $$(wc -c < $@) -le 16384 || (echo "kernel exceeds 32 sectors; raise KERNEL_SECTS"; exit 1)

os.img: boot.bin kernel.bin
	cat boot.bin kernel.bin > $@
	truncate -s 1M $@

run: os.img
	qemu-system-i386 -drive format=raw,file=os.img

clean:
	rm -f *.bin *.o os.img

.PHONY: all run clean
