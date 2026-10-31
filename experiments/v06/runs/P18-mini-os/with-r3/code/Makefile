CC       = i686-elf-gcc
LD       = i686-elf-ld
OBJCOPY ?= i686-elf-objcopy
NASM    ?= nasm
QEMU    ?= qemu-system-i386
KSECTORS = 32
CFLAGS  = -std=c99 -m32 -ffreestanding -nostdlib -fno-pic -fno-stack-protector -O2 -Wall -Wextra -Werror

.PHONY: all run clean
all: build/os.img

build/boot.bin: boot/boot.asm | build
	$(NASM) -f bin -DKSECTORS=$(KSECTORS) $< -o $@
build/entry.o: kernel/entry.asm | build
	$(NASM) -f elf32 $< -o $@
build/%.o: kernel/%.c kernel/vga.h | build
	$(CC) $(CFLAGS) -c $< -o $@
build/kernel.elf: build/entry.o build/kernel.o build/vga.o kernel/linker.ld
	$(LD) -m elf_i386 -nostdlib -T kernel/linker.ld -o $@ build/entry.o build/kernel.o build/vga.o
build/kernel.bin: build/kernel.elf
	$(OBJCOPY) -O binary $< $@
build/os.img: build/boot.bin build/kernel.bin
	cat build/boot.bin build/kernel.bin > $@
	truncate -s $$(( (1 + $(KSECTORS)) * 512 )) $@
build:
	mkdir -p build
run: build/os.img
	$(QEMU) -drive format=raw,file=build/os.img
clean:
	rm -rf build
