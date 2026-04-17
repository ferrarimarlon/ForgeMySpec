# CLAUDE.md — Mini OS

## Role
You are implementing a minimal x86 bare-metal OS from spec-first constraints.
Prioritize correctness at the hardware level, traceability, and keeping every
file under 300 lines.

## Persistent Memory Policy
Update only stable decisions and pitfalls here. No scratch logs.

## Spec Snapshot
- **Title**: Build a Simple x86 Operating System
- **Objective**: 512-byte BIOS bootloader + freestanding C kernel → VGA output → boots in QEMU.

## Non-Negotiable Guardrails
- Bootloader must be exactly 512 bytes ending in `0xAA55`.
- Kernel is freestanding C only — no libc, no crt0, no runtime.
- Zero external libraries; toolchain = nasm + gcc -m32 + ld.
- All files live inside `examples/mini-os/`.
- `make run` must be the single command to boot in QEMU.

## Decision Rules
- Boot.bin > 512 bytes → trim GDT or strings, never remove the magic bytes.
- Black screen in QEMU → check `0xAA55` at offset 510 and kernel load address `0x1000`.
- gcc -m32 fails → verify gcc-multilib is installed.
- Garbled VGA → verify `(attr << 8) | char` cell encoding.
- Linker emits ELF → add `--oformat binary` to ld invocation.

## Success Criteria
- `make` exits 0, produces `build/os.img`.
- `make run` boots QEMU and shows the kernel banner with coloured sections.
- `make clean` removes all artefacts.
- boot.bin is exactly 512 bytes; bytes 511-512 = `AA 55`.

## Assumptions
- Developer has nasm, gcc (multilib), binutils, qemu-system-x86_64.
- BIOS INT 13h available in 16-bit real mode for disk reads.
- Kernel loaded to physical address 0x1000 by the bootloader.
- VGA text framebuffer at physical address 0xB8000, 80×25 cells.

## Implementation Protocol
1. Read `spec.yaml` — implement only what is in `must_include`.
2. Write files in action order: a1 layout → a2 boot.asm → a3 kernel.c → a4 linker.ld → a5 Makefile.
3. After writing, run `make` and fix any build errors before moving on.
4. Run `make run` and verify QEMU output matches success criteria.
5. Report evidence (make output, QEMU screenshot description, file sizes).

## Decision Log
<!-- record stable architecture decisions here -->
- Kernel entry point is `kernel_main` (C), called directly via `call 0x1000` from the bootloader.
- GDT has three entries: null, code (0x08), data (0x10).
- Stack set to 0x90000 (576 KiB) — safely below the 640 KiB boundary.

## Known Pitfalls
- **Apple Silicon (arm64)**: `gcc -m32` is not supported. Use `i686-elf-gcc` cross-compiler (`brew install i686-elf-gcc i686-elf-binutils`).
- **Entry point ordering**: Without an explicit `entry.asm` stub in `.text.entry`, the C compiler places helper functions before `kernel_main` at the binary start. The bootloader's `call 0x1000` lands at a helper, not the kernel. Always link `entry.o` first.
- **Inline asm with `;`**: Apple Clang / i686-elf-gcc rejects `"cli; hlt"` as a single asm string. Use two separate `__asm__` calls.
- Forgetting `-fno-pie` causes gcc to emit position-independent code that breaks at fixed address 0x1000.
- `ld --oformat binary` must come before `-o` or it is silently ignored on some versions.
- `truncate -s` byte count must be a multiple of 512 that covers both boot.bin + kernel.bin.
