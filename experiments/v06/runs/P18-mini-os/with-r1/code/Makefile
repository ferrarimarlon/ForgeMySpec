# Mini OS: needs nasm, a freestanding i686 gcc/ld/objcopy and (to run) qemu.
CC       = i686-elf-gcc
LD       = i686-elf-ld
OBJCOPY  = i686-elf-objcopy
NASM    ?= nasm
QEMU    ?= qemu-system-i386

BUILD := build
CFLAGS := -std=gnu11 -O2 -Wall -Wextra -ffreestanding -fno-pic -fno-stack-protector -nostdlib -fno-builtin
KERNEL_MAX := 8192   # boot sector loads 16 sectors

all: $(BUILD)/os.img

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/boot.bin: boot/boot.asm | $(BUILD)
	$(NASM) -f bin $< -o $@

$(BUILD)/entry.o: kernel/entry.asm | $(BUILD)
	$(NASM) -f elf32 $< -o $@

$(BUILD)/kernel.o: kernel/kernel.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/kernel.elf: $(BUILD)/entry.o $(BUILD)/kernel.o kernel/linker.ld
	$(LD) -m elf_i386 -nostdlib -T kernel/linker.ld -o $@ $(BUILD)/entry.o $(BUILD)/kernel.o

$(BUILD)/kernel.bin: $(BUILD)/kernel.elf
	$(OBJCOPY) -O binary $< $@
	@test `wc -c < $@` -le $(KERNEL_MAX) || { echo "kernel exceeds $(KERNEL_MAX) bytes"; exit 1; }

# Boot sector + kernel, padded to a 1.44 MB floppy image.
$(BUILD)/os.img: $(BUILD)/boot.bin $(BUILD)/kernel.bin
	cat $^ > $@
	dd if=/dev/zero bs=1 count=0 seek=1474560 of=$@ 2>/dev/null

run: $(BUILD)/os.img
	$(QEMU) -drive format=raw,if=floppy,file=$<

clean:
	rm -rf $(BUILD)

.PHONY: all run clean
