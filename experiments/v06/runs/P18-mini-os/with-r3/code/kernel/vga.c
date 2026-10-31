#include "vga.h"

#define VGA_MEMORY ((volatile unsigned short *)0xB8000)
#define COLS 80
#define ROWS 25

static unsigned row, col;
static unsigned char attr = (VGA_BLACK << 4) | VGA_LIGHT_GREY;

static unsigned short cell(char c) { return (unsigned short)((attr << 8) | (unsigned char)c); }

void vga_set_color(enum vga_color fg, enum vga_color bg) { attr = (unsigned char)((bg << 4) | fg); }

void vga_clear(void) {
    for (unsigned i = 0; i < COLS * ROWS; i++) VGA_MEMORY[i] = cell(' ');
    row = col = 0;
}

static void scroll(void) {
    for (unsigned i = 0; i < COLS * (ROWS - 1); i++) VGA_MEMORY[i] = VGA_MEMORY[i + COLS];
    for (unsigned i = COLS * (ROWS - 1); i < COLS * ROWS; i++) VGA_MEMORY[i] = cell(' ');
    row = ROWS - 1;
}

void vga_putc(char c) {
    if (c == '\n') {
        col = 0;
        row++;
    } else {
        VGA_MEMORY[row * COLS + col] = cell(c);
        if (++col == COLS) { col = 0; row++; }
    }
    if (row >= ROWS) scroll();
}

void vga_puts(const char *s) { while (*s) vga_putc(*s++); }
