#include "vga.h"

void kmain(void) {
    vga_clear();
    vga_set_color(VGA_LIGHT_GREEN, VGA_BLACK);
    vga_puts("MiniOS booted: protected mode, VGA text output.\n");
    vga_set_color(VGA_LIGHT_GREY, VGA_BLACK);
    vga_puts("Bootloader + kernel, no external libraries.\n");
}
