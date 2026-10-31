CC      = i686-elf-gcc
LD      = i686-elf-ld
CFLAGS  = -m32 -ffreestanding -fno-pic -fno-stack-protector -nostdlib -O2 -Wall -Wextra

all: os.img

kernel.o: kernel.c
	$(CC) $(CFLAGS) -c $< -o $@
entry.o: entry.asm
	nasm -f elf32 $< -o $@
kernel.bin: entry.o kernel.o linker.ld
	$(LD) -T linker.ld --oformat binary entry.o kernel.o -o $@

os.img: boot.asm kernel.bin
	nasm -f bin -DKERNEL_SECTORS=$$(( ($$(stat -f %z kernel.bin) + 511) / 512 )) boot.asm -o boot.bin
	cat boot.bin kernel.bin > $@
	dd if=/dev/zero bs=512 count=4 >> $@ 2>/dev/null

run: os.img
	qemu-system-i386 -drive format=raw,file=os.img

clean:
	rm -f *.o *.bin os.img
