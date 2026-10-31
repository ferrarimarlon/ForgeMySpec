# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Mini x86 bare-metal OS
- Objective: Build a minimal x86 operating system (NASM bootloader plus freestanding C kernel) that prints text through VGA text mode, uses no external libraries and boots in QEMU.

## Non-Negotiable Guardrails
- No external libraries: freestanding C (-ffreestanding -nostdlib), no libc, no GRUB.
- No interrupts, paging, drivers other than VGA text, filesystem or userspace.
- Image fits a floppy-style raw disk image; no cross-platform support beyond x86 BIOS.

## Decision Rules
- If a toolchain tool is missing, stop and ask the user.
- Any feature beyond VGA text output is a spec amendment.

## Success Criteria
- make builds os.img from the bootloader and kernel without warnings-as-errors failing.
- qemu-system-i386 boots os.img and VGA text memory at 0xB8000 shows the kernel banner.

## Assumptions
- Target is 32-bit x86 BIOS boot, run with qemu-system-i386 (no UEFI).
- Tools nasm, i686-elf-gcc, i686-elf-ld, i686-elf-objcopy and qemu-system-i386 are on PATH.
- Kernel is small enough to be loaded by the boot sector via BIOS int 13h (at most 32 sectors).
- No keyboard input, interrupts, filesystem or multitasking: minimalist scope.

## Implementation Protocol
1. Read `spec.yaml` first and implement only traceable scope.
2. If details are missing, document explicit assumptions before coding.
3. Do not add features, frameworks, or layers outside the spec objective.
4. Verify all success criteria with concrete evidence (tests, commands, outputs).
5. Report residual risks and unresolved assumptions in the final summary.

## Decision Log
- (record stable architecture or policy decisions here)

## Known Pitfalls
- (record recurring implementation failure modes here)
