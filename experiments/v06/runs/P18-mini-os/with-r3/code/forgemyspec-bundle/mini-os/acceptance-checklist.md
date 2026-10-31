# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: A minimal 32-bit x86 OS in the repository root: a 512-byte boot sector loads a freestanding C kernel, enters protected mode and prints text through VGA text memory at 0xB8000. Built with no external libraries and bootable in QEMU.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] make produces build/os.img from the sources with no warnings that fail the build.
- [ ] Booting build/os.img in QEMU shows the kernel banner in VGA text memory.

## Required Evidence
- [ ] Output of make showing build/os.img created.
- [ ] Test run output of the boundary tests passing, including the headless QEMU boot reading VGA memory.

## Decision Rules Compliance
- [ ] If QEMU cannot be run headless in the environment, stop and report instead of dropping the boot test.
- [ ] If the kernel outgrows the sectors the bootloader loads, raise the sector count in the Makefile, do not add features.
