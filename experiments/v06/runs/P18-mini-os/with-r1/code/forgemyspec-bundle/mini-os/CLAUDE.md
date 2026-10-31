# CLAUDE.md

## Role
You are implementing from spec-first constraints. Prioritize determinism, traceability, and quality.

## Persistent Memory Policy
- This file is project memory and should persist across sessions.
- Update only stable project knowledge (decisions, conventions, pitfalls).
- Do not store ephemeral logs or temporary debugging notes here.

## Current Spec Snapshot
- Title: Mini OS (x86 bare-metal, VGA text)
- Objective: Build a minimalist x86 bare-metal operating system made of a boot sector and a 32-bit kernel that prints text through VGA text mode, buildable without external libraries and bootable in QEMU.

## Non-Negotiable Guardrails
- No external libraries: no libc, no GRUB, no third-party code; the kernel is compiled freestanding and linked with nostdlib.
- Out of scope: interrupts, keyboard input, memory management, multitasking, filesystems, 64-bit mode, UEFI.
- Build artifacts go to a build directory that is git-ignored.

## Decision Rules
- If the kernel outgrows the sectors the boot sector loads, stop and amend the spec rather than silently raising limits.
- If QEMU or the cross compiler is missing, stop and ask the user.

## Success Criteria
- make produces a disk image whose first sector is a 512-byte boot sector ending with 0x55AA.
- QEMU boots the image and the VGA buffer shows the kernel banner.

## Assumptions
- Toolchain is nasm for the boot sector and i686-elf-gcc/ld for the freestanding kernel.
- Target machine is a 32-bit x86 PC booted by legacy BIOS from a floppy-style disk image.
- The kernel is small enough to be loaded by the boot sector with BIOS int 13h CHS reads.
- The VGA text buffer is 80x25 cells of two bytes (character, attribute) at physical address 0xB8000.

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
