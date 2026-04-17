/*
 * kernel.c  —  Freestanding x86 kernel (32-bit protected mode)
 *
 * No libc.  No runtime.  VGA text-mode output only.
 *
 * Compile:
 *   gcc -m32 -ffreestanding -fno-pie -nostdlib -nostdinc -O2 -c \
 *       -o build/kernel.o kernel/kernel.c
 */

/* ── QEMU debug port (0xE9) — writes appear on stdout with -debugcon stdio ── */
static inline void dbg(char c)
{
    __asm__ volatile ("outb %0, $0xE9" : : "a"(c));
}
static void dbg_str(const char *s) { while (*s) dbg(*s++); }

/* ── VGA text-mode constants ─────────────────────────────────────────────── */
#define VGA_BASE  ((volatile unsigned short *)0xB8000)
#define COLS      80
#define ROWS      25

/* Colour nibbles: high = background, low = foreground */
#define BLACK   0x0
#define BLUE    0x1
#define GREEN   0x2
#define CYAN    0x3
#define RED     0x4
#define BROWN   0x6
#define LGRAY   0x7
#define DGRAY   0x8
#define LGREEN  0xA
#define LCYAN   0xB
#define YELLOW  0xE
#define WHITE   0xF

#define ATTR(fg, bg)  (unsigned char)(((bg) << 4) | (fg))

/* ── Cursor state ────────────────────────────────────────────────────────── */
static int cur_col = 0;
static int cur_row = 0;

/* ── vga_clear ───────────────────────────────────────────────────────────── */
static void vga_clear(void)
{
    volatile unsigned short *fb = VGA_BASE;
    unsigned short blank = (unsigned short)((ATTR(LGRAY, BLACK) << 8) | ' ');
    for (int i = 0; i < COLS * ROWS; i++)
        fb[i] = blank;
    cur_col = 0;
    cur_row = 0;
}

/* ── vga_scroll  (shift all rows up by 1, blank last row) ───────────────── */
static void vga_scroll(void)
{
    volatile unsigned short *fb = VGA_BASE;
    for (int r = 1; r < ROWS; r++)
        for (int c = 0; c < COLS; c++)
            fb[(r - 1) * COLS + c] = fb[r * COLS + c];
    unsigned short blank = (unsigned short)((ATTR(LGRAY, BLACK) << 8) | ' ');
    for (int c = 0; c < COLS; c++)
        fb[(ROWS - 1) * COLS + c] = blank;
    cur_row = ROWS - 1;
}

/* ── vga_putchar ─────────────────────────────────────────────────────────── */
static void vga_putchar(char ch, unsigned char attr)
{
    volatile unsigned short *fb = VGA_BASE;
    if (ch == '\n') {
        cur_col = 0;
        cur_row++;
    } else {
        fb[cur_row * COLS + cur_col] =
            (unsigned short)((attr << 8) | (unsigned char)ch);
        if (++cur_col >= COLS) { cur_col = 0; cur_row++; }
    }
    if (cur_row >= ROWS) vga_scroll();
}

/* ── print ───────────────────────────────────────────────────────────────── */
static void print(const char *s, unsigned char attr)
{
    while (*s) vga_putchar(*s++, attr);
}

/* ── print_uint (base-10) ────────────────────────────────────────────────── */
static void print_uint(unsigned int n, unsigned char attr)
{
    char buf[11];
    int  i = 10;
    buf[10] = '\0';
    if (n == 0) { vga_putchar('0', attr); return; }
    while (n) { buf[--i] = (char)('0' + n % 10); n /= 10; }
    print(buf + i, attr);
}

/* ── print_hex (8 hex digits, 0x prefix) ────────────────────────────────── */
static void print_hex(unsigned int n, unsigned char attr)
{
    static const char h[] = "0123456789ABCDEF";
    char buf[9];
    buf[8] = '\0';
    for (int i = 7; i >= 0; i--) { buf[i] = h[n & 0xF]; n >>= 4; }
    print("0x", attr);
    print(buf, attr);
}

/* ── hline  (full-width horizontal rule) ────────────────────────────────── */
static void hline(char ch, unsigned char attr)
{
    for (int i = 0; i < COLS; i++) vga_putchar(ch, attr);
}

/* ── pad (print spaces to reach column x) ───────────────────────────────── */
static void pad(int spaces, unsigned char attr)
{
    for (int i = 0; i < spaces; i++) vga_putchar(' ', attr);
}

/* ═══════════════════════════════════════════════════════════════════════════
 * kernel_main  —  called by the bootloader (call 0x1000)
 * ═══════════════════════════════════════════════════════════════════════════ */
void kernel_main(void)
{
    vga_clear();

    /* Mirror key output to QEMU debug port (-debugcon stdio) */
    dbg_str("MiniOS v0.1 — kernel_main reached\n");
    dbg_str("[BOOT] Bootloader: 0x7C00  Kernel: 0x1000  Stack: 0x90000\n");
    dbg_str("[MEM]  VGA: 0xB8000  Conv: 0x00000-0x9FFFF\n");
    dbg_str("[GDT]  Code: 0x08  Data: 0x10\n");
    dbg_str("Kernel halted. All systems nominal.\n");

    /* ── Header bar ──────────────────────────────────────────────────────── */
    hline(' ', ATTR(BLACK, CYAN));
    cur_col = 0; cur_row = 0;
    pad(2,  ATTR(WHITE, CYAN));
    print("MiniOS  v0.1", ATTR(WHITE,  CYAN));
    pad(43, ATTR(BLACK, CYAN));
    print("x86 | 32-bit PM | VGA 80x25", ATTR(YELLOW, CYAN));
    pad(1,  ATTR(BLACK, CYAN));
    cur_col = 0; cur_row = 1;

    hline('=', ATTR(CYAN, BLACK));

    /* ── Boot info section ───────────────────────────────────────────────── */
    unsigned char lbl = ATTR(LGREEN, BLACK);
    unsigned char val = ATTR(WHITE,  BLACK);
    unsigned char dim = ATTR(DGRAY,  BLACK);

    print("\n", 0);
    print("  [BOOT] ", lbl);  print("Bootloader  ", dim);
    print_hex(0x7C00, val);   print("  (MBR, 512 bytes)\n", dim);

    print("  [BOOT] ", lbl);  print("Kernel      ", dim);
    print_hex(0x1000, val);   print("  (loaded by INT 13h)\n", dim);

    print("  [BOOT] ", lbl);  print("Stack top   ", dim);
    print_hex(0x90000, val);  print("  (576 KiB)\n", dim);

    /* ── Memory map ──────────────────────────────────────────────────────── */
    print("\n", 0);
    hline('-', ATTR(DGRAY, BLACK));

    print("\n  [MEM]  ", lbl);
    print("Conventional    ", dim);
    print("0x00000000", val); print(" - ", dim); print("0x0009FFFF", val);
    print("  640 KiB\n", dim);

    print("  [MEM]  ", lbl);
    print("VGA framebuf    ", dim);
    print_hex(0xB8000, val);
    print("  (", dim); print_uint(COLS, val);
    print(" x ", dim); print_uint(ROWS, val); print(" cells)\n", dim);

    print("  [MEM]  ", lbl);
    print("ROM / BIOS      ", dim);
    print("0x000A0000", val); print(" - ", dim);
    print("0x000FFFFF\n", val);

    /* ── GDT info ────────────────────────────────────────────────────────── */
    print("\n", 0);
    hline('-', ATTR(DGRAY, BLACK));

    print("\n  [GDT]  ", lbl);
    print("Null            sel=", dim); print_hex(0x00, val); print("\n", 0);

    print("  [GDT]  ", lbl);
    print("Code  32-bit    sel=", dim); print_hex(0x08, val);
    print("  base=0x0  limit=4G\n", dim);

    print("  [GDT]  ", lbl);
    print("Data  32-bit    sel=", dim); print_hex(0x10, val);
    print("  base=0x0  limit=4G\n", dim);

    /* ── Footer ──────────────────────────────────────────────────────────── */
    print("\n", 0);
    hline('=', ATTR(CYAN, BLACK));
    print("\n  Kernel halted. ", ATTR(LGRAY, BLACK));
    print("All systems nominal.\n", ATTR(LGREEN, BLACK));
    hline('-', ATTR(DGRAY, BLACK));

    /* ── CPU halt ────────────────────────────────────────────────────────── */
    for (;;) { __asm__ volatile ("cli"); __asm__ volatile ("hlt"); }
}
