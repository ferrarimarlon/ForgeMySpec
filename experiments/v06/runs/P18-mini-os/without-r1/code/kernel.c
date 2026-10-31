/* Minimal kernel: VGA text console, polled PS/2 keyboard, tiny shell. */
typedef unsigned char u8;
typedef unsigned short u16;

#define VGA ((volatile u16 *)0xB8000)
#define COLS 80
#define ROWS 25

static int cx, cy;
static u8 color = 0x07;

static inline void outb(u16 p, u8 v) { __asm__ volatile("outb %0,%1" :: "a"(v), "Nd"(p)); }
static inline u8 inb(u16 p) { u8 v; __asm__ volatile("inb %1,%0" : "=a"(v) : "Nd"(p)); return v; }

static void cursor(void) {
    u16 pos = cy * COLS + cx;
    outb(0x3D4, 14); outb(0x3D5, pos >> 8);
    outb(0x3D4, 15); outb(0x3D5, pos & 0xFF);
}

static void clear(void) {
    for (int i = 0; i < COLS * ROWS; i++) VGA[i] = (color << 8) | ' ';
    cx = cy = 0;
}

static void scroll(void) {
    for (int i = 0; i < COLS * (ROWS - 1); i++) VGA[i] = VGA[i + COLS];
    for (int i = 0; i < COLS; i++) VGA[COLS * (ROWS - 1) + i] = (color << 8) | ' ';
    cy = ROWS - 1;
}

static void putc(char c) {
    if (c == '\n') { cx = 0; cy++; }
    else if (c == '\b') { if (cx > 0) { cx--; VGA[cy * COLS + cx] = (color << 8) | ' '; } }
    else {
        VGA[cy * COLS + cx] = (color << 8) | (u8)c;
        if (++cx == COLS) { cx = 0; cy++; }
    }
    if (cy >= ROWS) scroll();
    cursor();
}

static void puts(const char *s) { while (*s) putc(*s++); }

static int streq(const char *a, const char *b) {
    while (*a && *a == *b) a++, b++;
    return *a == *b;
}

static const char keymap[128] = {
    0, 27, '1','2','3','4','5','6','7','8','9','0','-','=','\b',
    '\t','q','w','e','r','t','y','u','i','o','p','[',']','\n',
    0,'a','s','d','f','g','h','j','k','l',';','\'','`',
    0,'\\','z','x','c','v','b','n','m',',','.','/',0,'*',0,' '
};

static char getc(void) {
    for (;;) {
        while (!(inb(0x64) & 1)) ;
        u8 sc = inb(0x60);
        if (sc & 0x80) continue;          /* key release */
        if (sc < 128 && keymap[sc]) return keymap[sc];
    }
}

static void reboot(void) {
    while (inb(0x64) & 2) ;
    outb(0x64, 0xFE);
}

static void halt(void) {
    puts("System halted.\n");
    for (;;) __asm__ volatile("cli; hlt");
}

void kmain(void) {
    char buf[64];
    clear();
    color = 0x0A;
    puts("MiniOS 0.1 - x86 protected mode\n");
    color = 0x07;
    puts("Type 'help' for commands.\n\n");

    for (;;) {
        puts("> ");
        int n = 0;
        for (;;) {
            char c = getc();
            if (c == '\n') { putc('\n'); break; }
            if (c == '\b') { if (n) { n--; putc('\b'); } }
            else if (n < 63 && c >= ' ') { buf[n++] = c; putc(c); }
        }
        buf[n] = 0;

        if (streq(buf, "help")) puts("help clear about color reboot halt\n");
        else if (streq(buf, "clear")) clear();
        else if (streq(buf, "about")) puts("MiniOS: bootloader + C kernel, VGA text, no libs.\n");
        else if (streq(buf, "color")) { color = (color == 0x07) ? 0x1E : 0x07; puts("Color changed.\n"); }
        else if (streq(buf, "reboot")) reboot();
        else if (streq(buf, "halt")) halt();
        else if (n) { puts("Unknown command: "); puts(buf); putc('\n'); }
    }
}
