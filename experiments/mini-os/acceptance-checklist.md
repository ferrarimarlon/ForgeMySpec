# Acceptance Checklist — Mini OS

## Scope Verification
- [x] All `must_include` items are present: bootloader, protected-mode switch, C kernel, VGA output, Makefile, QEMU target.
- [x] No `must_not_include` items added: no libc, no filesystem, no interrupts, no scheduler, no files outside `examples/mini-os/`.

## Build
- [x] `make` exits with code 0.
- [x] `build/boot.bin` exists and is exactly **512 bytes**.  `wc -c` → 512
- [x] `build/kernel.bin` exists.  2445 bytes
- [x] `build/os.img` exists.  65536 bytes
- [x] Bytes at offset 510–511 of `build/os.img` are `55 AA`.  `xxd -s 510 -l 2` → `55aa`

## Boot & Output (verified via QEMU debug port)
- [x] QEMU kernel reached — debug port confirms `kernel_main` executed.
- [x] OS name displayed: `MiniOS v0.1 — kernel_main reached`
- [x] Boot addresses: `[BOOT] Bootloader: 0x7C00  Kernel: 0x1000  Stack: 0x90000`
- [x] Memory map: `[MEM]  VGA: 0xB8000  Conv: 0x00000-0x9FFFF`
- [x] GDT selectors: `[GDT]  Code: 0x08  Data: 0x10`
- [x] Footer: `Kernel halted. All systems nominal.`
- [x] VGA framebuffer writes use multiple colours (CYAN header, LGREEN labels, WHITE values, DGRAY separators).

## Clean
- [x] `make clean` removes `build/` without errors.
- [x] No generated artefacts remain after clean.

## Code Quality
- [x] No source file exceeds 300 lines.
- [x] No external libraries or libc headers included.
- [x] Bootloader assembled with `nasm -f bin`.
- [x] Kernel compiled with `-ffreestanding -nostdlib -nostdinc`.

## Required Evidence

```
$ make
  [OK] boot.bin       512 bytes
  [OK] kernel.bin      2445 bytes
  [OK] os.img     65536 bytes
  [OK] magic   55aa

$ wc -c build/boot.bin
     512 build/boot.bin

$ xxd -s 510 -l 2 build/os.img
000001fe: 55aa

$ qemu debug port output:
MiniOS v0.1 — kernel_main reached
[BOOT] Bootloader: 0x7C00  Kernel: 0x1000  Stack: 0x90000
[MEM]  VGA: 0xB8000  Conv: 0x00000-0x9FFFF
[GDT]  Code: 0x08  Data: 0x10
Kernel halted. All systems nominal.
```
