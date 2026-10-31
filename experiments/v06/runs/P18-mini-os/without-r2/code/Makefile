CC = i686-elf-gcc
LD = i686-elf-ld
CFLAGS = -m32 -ffreestanding -fno-pic -fno-stack-protector -O2 -Wall -nostdlib

all: os.img

build/boot.bin: src/boot.asm
	@mkdir -p build && nasm -f bin $< -o $@
build/entry.o: src/entry.asm
	@mkdir -p build && nasm -f elf32 $< -o $@
build/kernel.o: src/kernel.c
	@mkdir -p build && $(CC) $(CFLAGS) -c $< -o $@
build/kernel.bin: build/entry.o build/kernel.o src/link.ld
	$(LD) -m elf_i386 -T src/link.ld --oformat binary -o $@ build/entry.o build/kernel.o

os.img: build/boot.bin build/kernel.bin
	cat build/boot.bin build/kernel.bin > $@
	@sz=$$(stat -f%z $@ 2>/dev/null || stat -c%s $@); \
	  [ $$sz -le 9216 ] || { echo "kernel too big for loader (17 sectors)"; exit 1; }
	truncate -s 1474560 $@

run: os.img
	qemu-system-i386 -drive format=raw,if=floppy,file=os.img

clean:
	rm -rf build os.img
.PHONY: all run clean
