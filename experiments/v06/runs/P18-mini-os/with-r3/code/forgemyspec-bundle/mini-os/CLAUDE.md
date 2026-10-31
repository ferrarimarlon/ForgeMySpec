# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Mini OS: x86 bare-metal bootloader and kernel with VGA text output
- Objective: A minimal 32-bit x86 OS in the repository root: a 512-byte boot sector loads a freestanding C kernel, enters protected mode and prints text through VGA text memory at 0xB8000. Built with no external libraries and bootable in QEMU.

## Non-Negotiable Guardrails
- No external libraries: freestanding C (-ffreestanding -nostdlib), no libc, no GRUB.
- No keyboard driver, interrupts, paging, filesystem or multitasking.
- Boot sector is exactly 512 bytes and ends with the 0x55AA signature.
- Sources live in boot/, kernel/, Makefile and tests/; build output goes to build/.

## Decision Rules
- If QEMU cannot be run headless in the environment, stop and report instead of dropping the boot test.
- If the kernel outgrows the sectors the bootloader loads, raise the sector count in the Makefile, do not add features.

## Success Criteria
- make produces build/os.img from the sources with no warnings that fail the build.
- Booting build/os.img in QEMU shows the kernel banner in VGA text memory.

## Assumptions
- The user accepts a BIOS legacy boot (floppy/disk image) on qemu-system-i386, not UEFI.
- The cross toolchain i686-elf-gcc and nasm in /opt/homebrew/bin are the build tools.
- Minimal means: boot sector, protected mode switch, VGA text driver, a banner; no interrupts, keyboard or filesystem.

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
