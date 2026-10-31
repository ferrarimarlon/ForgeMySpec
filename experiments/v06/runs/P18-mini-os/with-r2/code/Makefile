# Everything is built under os/build; the bootable image is os/build/os.img
CC      = i686-elf-gcc
LD      = i686-elf-ld
OBJCOPY = i686-elf-objcopy
CFLAGS  = -std=c11 -m32 -ffreestanding -nostdlib -fno-pic -fno-stack-protector -O2 -Wall -Wextra
SECTORS = 32
B       = os/build

all: $(B)/os.img

$(B)/boot.bin: os/boot.asm | $(B)
	nasm -f bin $< -o $@

$(B)/kernel.o: os/kernel.c | $(B)
	$(CC) $(CFLAGS) -c $< -o $@

$(B)/kernel.elf: $(B)/kernel.o os/linker.ld
	$(LD) -m elf_i386 -T os/linker.ld -nostdlib -o $@ $(B)/kernel.o

$(B)/kernel.bin: $(B)/kernel.elf
	$(OBJCOPY) -O binary $< $@
	dd if=/dev/zero of=$@ bs=512 count=0 seek=$(SECTORS) 2>/dev/null

$(B)/os.img: $(B)/boot.bin $(B)/kernel.bin
	cat $(B)/boot.bin $(B)/kernel.bin > $@

$(B):
	mkdir -p $(B)

run: $(B)/os.img
	qemu-system-i386 -drive format=raw,file=$(B)/os.img

clean:
	rm -rf $(B)

.PHONY: all run clean
