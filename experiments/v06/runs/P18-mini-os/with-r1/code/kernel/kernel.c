/* Mini OS kernel: freestanding C, VGA text output at 0xB8000. */

typedef unsigned char  u8;
typedef unsigned short u16;

#define VGA_MEMORY ((volatile u16 *)0xB8000)
#define VGA_COLS   80
#define VGA_ROWS   25

enum vga_color {
    VGA_BLACK = 0, VGA_BLUE, VGA_GREEN, VGA_CYAN, VGA_RED, VGA_MAGENTA,
    VGA_BROWN, VGA_LIGHT_GREY, VGA_DARK_GREY, VGA_LIGHT_BLUE,
    VGA_LIGHT_GREEN, VGA_LIGHT_CYAN, VGA_LIGHT_RED, VGA_LIGHT_MAGENTA,
    VGA_YELLOW, VGA_WHITE
};

static int row, col;
static u8 attr;

static u16 cell(char c, u8 a) { return (u16)((u16)a << 8) | (u8)c; }

static void set_color(enum vga_color fg, enum vga_color bg)
{
    attr = (u8)(fg | (bg << 4));
}

static void outb(u16 port, u8 v)
{
    __asm__ volatile ("outb %0, %1" : : "a"(v), "Nd"(port));
}

static void update_cursor(void)
{
    u16 pos = (u16)(row * VGA_COLS + col);
    outb(0x3D4, 14); outb(0x3D5, (u8)(pos >> 8));
    outb(0x3D4, 15); outb(0x3D5, (u8)(pos & 0xFF));
}

static void clear(void)
{
    for (int i = 0; i < VGA_COLS * VGA_ROWS; i++)
        VGA_MEMORY[i] = cell(' ', attr);
    row = col = 0;
}

static void scroll(void)
{
    for (int i = 0; i < VGA_COLS * (VGA_ROWS - 1); i++)
        VGA_MEMORY[i] = VGA_MEMORY[i + VGA_COLS];
    for (int i = VGA_COLS * (VGA_ROWS - 1); i < VGA_COLS * VGA_ROWS; i++)
        VGA_MEMORY[i] = cell(' ', attr);
    row = VGA_ROWS - 1;
}

static void newline(void)
{
    col = 0;
    if (++row >= VGA_ROWS)
        scroll();
}

static void putc(char c)
{
    if (c == '\n') {
        newline();
    } else {
        VGA_MEMORY[row * VGA_COLS + col] = cell(c, attr);
        if (++col >= VGA_COLS)
            newline();
    }
}

static void puts(const char *s)
{
    while (*s)
        putc(*s++);
    update_cursor();
}

void kmain(void)
{
    set_color(VGA_LIGHT_GREY, VGA_BLACK);
    clear();

    set_color(VGA_LIGHT_GREEN, VGA_BLACK);
    puts("MiniOS kernel loaded\n");
    set_color(VGA_LIGHT_GREY, VGA_BLACK);
    puts("Booted from a 512-byte boot sector into 32-bit protected mode.\n");
    puts("VGA text output at 0xB8000. Halting.\n");
}
