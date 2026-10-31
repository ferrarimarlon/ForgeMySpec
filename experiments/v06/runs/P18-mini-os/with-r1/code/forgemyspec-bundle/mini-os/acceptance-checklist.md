# Acceptance Checklist

## Scope
- [ ] Objective implemented exactly: Build a minimalist x86 bare-metal operating system made of a boot sector and a 32-bit kernel that prints text through VGA text mode, buildable without external libraries and bootable in QEMU.
- [ ] No unrequested features were introduced
- [ ] All assumptions are explicit and justified

## Success Criteria
- [ ] make produces a disk image whose first sector is a 512-byte boot sector ending with 0x55AA.
- [ ] QEMU boots the image and the VGA buffer shows the kernel banner.

## Required Evidence
- [ ] Output of make showing the image is built.
- [ ] Output of python3 -m unittest discover tests passing, including the QEMU boot test that reads VGA memory.

## Decision Rules Compliance
- [ ] If the kernel outgrows the sectors the boot sector loads, stop and amend the spec rather than silently raising limits.
- [ ] If QEMU or the cross compiler is missing, stop and ask the user.
