/* Freestanding kernel: VGA text mode driver (80x25 at 0xB8000). */
typedef unsigned char u8;
typedef unsigned short u16;

#define VGA_MEM   ((volatile u16 *)0xB8000)
#define VGA_COLS  80
#define VGA_ROWS  25
#define ATTR_DEFAULT 0x07
#define ATTR_TITLE   0x1F

static int cur_row, cur_col;

static u16 cell(char c, u8 attr) { return (u16)((attr << 8) | (u8)c); }

static void vga_clear(u8 attr)
{
    for (int i = 0; i < VGA_COLS * VGA_ROWS; i++)
        VGA_MEM[i] = cell(' ', attr);
    cur_row = cur_col = 0;
}

static void vga_scroll(void)
{
    for (int i = 0; i < VGA_COLS * (VGA_ROWS - 1); i++)
        VGA_MEM[i] = VGA_MEM[i + VGA_COLS];
    for (int i = 0; i < VGA_COLS; i++)
        VGA_MEM[VGA_COLS * (VGA_ROWS - 1) + i] = cell(' ', ATTR_DEFAULT);
    cur_row = VGA_ROWS - 1;
}

static void vga_putc(char c, u8 attr)
{
    if (c == '\n') {
        cur_col = 0;
        cur_row++;
    } else {
        VGA_MEM[cur_row * VGA_COLS + cur_col] = cell(c, attr);
        if (++cur_col == VGA_COLS) {
            cur_col = 0;
            cur_row++;
        }
    }
    if (cur_row >= VGA_ROWS)
        vga_scroll();
}

static void vga_puts(const char *s, u8 attr)
{
    while (*s)
        vga_putc(*s++, attr);
}

__attribute__((section(".text.entry"), noreturn))
void kmain(void)
{
    vga_clear(ATTR_DEFAULT);
    vga_puts("MiniOS 0.1 - booted in 32-bit protected mode\n", ATTR_TITLE);
    vga_puts("VGA text output works. Halting.\n", ATTR_DEFAULT);
    for (;;)
        __asm__ volatile ("hlt");
}
