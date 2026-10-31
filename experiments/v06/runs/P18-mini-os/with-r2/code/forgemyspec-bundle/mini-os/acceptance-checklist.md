# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Build a minimal x86 operating system (NASM bootloader plus freestanding C kernel) that prints text through VGA text mode, uses no external libraries and boots in QEMU.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] make builds os.img from the bootloader and kernel without warnings-as-errors failing.
- [ ] qemu-system-i386 boots os.img and VGA text memory at 0xB8000 shows the kernel banner.

## Required Evidence
- [ ] Output of make showing os.img produced.
- [ ] Unittest run output for tests_os passing, including the QEMU boot test.
- [ ] QEMU monitor memory dump of 0xB8000 containing the banner text.

## Decision Rules Compliance
- [ ] If a toolchain tool is missing, stop and ask the user.
- [ ] Any feature beyond VGA text output is a spec amendment.
