# =============================================================================
# Makefile  —  Mini OS build system
#
# Targets:
#   all    (default)  build/os.img
#   run               boot in QEMU (press Ctrl-A X to quit)
#   clean             remove build/
#
# Requirements:
#   nasm               assembler
#   gcc -m32           freestanding C compiler (brew install gcc / apt gcc-multilib)
#   ld  -m elf_i386    linker  (part of binutils)
#   qemu-system-x86_64 emulator
# =============================================================================

ASM   := nasm
# On Apple Silicon (arm64) use the i686-elf cross-compiler.
# On Linux x86 you can use:  CC=gcc  CFLAGS=-m32 ...  LD=ld  LDFLAGS=-m elf_i386
CC    := i686-elf-gcc
LD    := i686-elf-ld

CFLAGS  := -ffreestanding -fno-pie -fno-stack-protector \
           -nostdlib -nostdinc -O2 -Wall -Wextra

BUILD   := build
BOOT_S  := boot/boot.asm
KERNEL_C := kernel/kernel.c

BOOT_BIN   := $(BUILD)/boot.bin
ENTRY_O    := $(BUILD)/entry.o
KERNEL_O   := $(BUILD)/kernel.o
KERNEL_BIN := $(BUILD)/kernel.bin
OS_IMG     := $(BUILD)/os.img

# Image size: must hold boot (512 B) + kernel; pad to 64 KiB for BIOS reads
IMG_SIZE  := 65536

.PHONY: all run clean

# ── Default target ────────────────────────────────────────────────────────────
all: $(OS_IMG)

# ── Bootloader ────────────────────────────────────────────────────────────────
$(BOOT_BIN): $(BOOT_S) | $(BUILD)
	$(ASM) -f bin -o $@ $<
	@size=$$(wc -c < $@); \
	 if [ "$$size" -ne 512 ]; then \
	   echo "ERROR: boot.bin is $$size bytes (must be exactly 512)"; exit 1; \
	 fi
	@echo "  [OK] boot.bin  $$(wc -c < $@) bytes"

# ── Entry point object (linked first to sit at 0x1000) ───────────────────────
$(ENTRY_O): kernel/entry.asm | $(BUILD)
	$(ASM) -f elf32 -o $@ $<

# ── Kernel C object ───────────────────────────────────────────────────────────
$(KERNEL_O): $(KERNEL_C) | $(BUILD)
	$(CC) $(CFLAGS) -c -o $@ $<

# ── Kernel flat binary ────────────────────────────────────────────────────────
$(KERNEL_BIN): $(ENTRY_O) $(KERNEL_O) linker.ld
	$(LD) --oformat binary -T linker.ld -o $@ $(ENTRY_O) $(KERNEL_O)
	@echo "  [OK] kernel.bin  $$(wc -c < $@) bytes"

# ── Disk image (boot + kernel, padded) ───────────────────────────────────────
$(OS_IMG): $(BOOT_BIN) $(KERNEL_BIN)
	cat $(BOOT_BIN) $(KERNEL_BIN) > $@
	truncate -s $(IMG_SIZE) $@
	@echo "  [OK] os.img  $$(wc -c < $@) bytes"
	@echo "  [OK] magic   $$(xxd -s 510 -l 2 $@ | awk '{print $$2}')"

# ── Build directory ───────────────────────────────────────────────────────────
$(BUILD):
	mkdir -p $(BUILD)

# ── Run in QEMU ───────────────────────────────────────────────────────────────
run: $(OS_IMG)
	@echo "Booting in QEMU  (Ctrl-A X to quit)"
	qemu-system-x86_64 \
	    -drive format=raw,file=$(OS_IMG) \
	    -nographic \
	    -debugcon stdio \
	    -no-reboot

# Run with a graphical window (VGA output visible)
run-gui: $(OS_IMG)
	qemu-system-x86_64 \
	    -drive format=raw,file=$(OS_IMG) \
	    -debugcon stdio \
	    -no-reboot

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf $(BUILD)
	@echo "  [OK] build/ removed"
