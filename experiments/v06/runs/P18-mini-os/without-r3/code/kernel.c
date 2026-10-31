/* Minimal kernel: VGA text console, polled PS/2 keyboard, tiny shell. */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

#define VGA ((volatile u16 *)0xb8000)
#define COLS 80
#define ROWS 25

static int cx, cy;
static u8 attr = 0x07;

static inline u8 inb(u16 p) { u8 v; __asm__ volatile("inb %1,%0" : "=a"(v) : "Nd"(p)); return v; }
static inline void outb(u16 p, u8 v) { __asm__ volatile("outb %0,%1" : : "a"(v), "Nd"(p)); }

static void cursor(void) {
    u16 pos = cy * COLS + cx;
    outb(0x3d4, 14); outb(0x3d5, pos >> 8);
    outb(0x3d4, 15); outb(0x3d5, pos & 0xff);
}

static void clear(void) {
    for (int i = 0; i < COLS * ROWS; i++) VGA[i] = attr << 8 | ' ';
    cx = cy = 0;
    cursor();
}

static void scroll(void) {
    for (int i = 0; i < COLS * (ROWS - 1); i++) VGA[i] = VGA[i + COLS];
    for (int i = COLS * (ROWS - 1); i < COLS * ROWS; i++) VGA[i] = attr << 8 | ' ';
    cy = ROWS - 1;
}

static void putc(char c) {
    if (c == '\n') { cx = 0; cy++; }
    else if (c == '\b') { if (cx) { cx--; VGA[cy * COLS + cx] = attr << 8 | ' '; } }
    else {
        VGA[cy * COLS + cx] = attr << 8 | (u8)c;
        if (++cx == COLS) { cx = 0; cy++; }
    }
    if (cy == ROWS) scroll();
    cursor();
}

static void puts(const char *s) { while (*s) putc(*s++); }

static void putu(u32 n) {
    char b[11]; int i = 10;
    b[i] = 0;
    do { b[--i] = '0' + n % 10; n /= 10; } while (n);
    puts(b + i);
}

static void puthex(u32 n) {
    puts("0x");
    for (int i = 28; i >= 0; i -= 4) putc("0123456789abcdef"[(n >> i) & 15]);
}

static int streq(const char *a, const char *b) {
    while (*a && *a == *b) a++, b++;
    return *a == *b;
}

static const char keymap[128] = {
    0, 27, '1','2','3','4','5','6','7','8','9','0','-','=', '\b',
    '\t','q','w','e','r','t','y','u','i','o','p','[',']','\n',
    0,'a','s','d','f','g','h','j','k','l',';','\'','`',
    0,'\\','z','x','c','v','b','n','m',',','.','/',0,'*',0,' '
};
static const char keymap_sh[128] = {
    0, 27, '!','@','#','$','%','^','&','*','(',')','_','+', '\b',
    '\t','Q','W','E','R','T','Y','U','I','O','P','{','}','\n',
    0,'A','S','D','F','G','H','J','K','L',':','"','~',
    0,'|','Z','X','C','V','B','N','M','<','>','?',0,'*',0,' '
};

static char getc(void) {
    static int shift;
    for (;;) {
        while (!(inb(0x64) & 1)) __asm__ volatile("pause");
        u8 sc = inb(0x60);
        if (sc == 0x2a || sc == 0x36) { shift = 1; continue; }
        if (sc == 0xaa || sc == 0xb6) { shift = 0; continue; }
        if (sc & 0x80) continue;
        char c = (shift ? keymap_sh : keymap)[sc];
        if (c) return c;
    }
}

/* Read counter via PIT latch to give a crude uptime-ish value. */
static u32 ticks(void) {
    u32 lo, hi;
    __asm__ volatile("rdtsc" : "=a"(lo), "=d"(hi));
    return hi;
}

static void cmd_mem(void) {
    /* Probe CMOS for base/extended memory sizes (KB). */
    outb(0x70, 0x30); u32 lo = inb(0x71);
    outb(0x70, 0x31); u32 hi = inb(0x71);
    puts("Extended memory: "); putu(lo | hi << 8); puts(" KB\n");
}

static void shell(void) {
    char buf[80];
    for (;;) {
        puts("> ");
        int n = 0;
        for (;;) {
            char c = getc();
            if (c == '\n') { putc('\n'); break; }
            if (c == '\b') { if (n) { n--; putc('\b'); } continue; }
            if (n < 79 && c >= ' ') { buf[n++] = c; putc(c); }
        }
        buf[n] = 0;
        if (!n) continue;
        if (streq(buf, "help")) puts("Commands: help clear mem color ticks halt\n");
        else if (streq(buf, "clear")) clear();
        else if (streq(buf, "mem")) cmd_mem();
        else if (streq(buf, "color")) { attr = attr == 0x07 ? 0x0a : attr == 0x0a ? 0x0e : 0x07; puts("Color changed\n"); }
        else if (streq(buf, "ticks")) { puts("TSC high: "); puthex(ticks()); putc('\n'); }
        else if (streq(buf, "halt")) { puts("System halted.\n"); for (;;) __asm__ volatile("cli; hlt"); }
        else { puts("Unknown command: "); puts(buf); putc('\n'); }
    }
}

void kmain(void) {
    clear();
    puts("MiniOS v0.1 - 32-bit protected mode\n");
    puts("Type 'help' for commands.\n\n");
    shell();
}
