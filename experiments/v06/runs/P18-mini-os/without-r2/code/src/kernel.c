typedef unsigned char u8;
typedef unsigned short u16;

#define VGA ((volatile u16 *)0xB8000)
#define COLS 80
#define ROWS 25

static int cx, cy;
static u8 color = 0x0F;

static u8 inb(u16 p) { u8 v; __asm__ volatile("inb %1,%0" : "=a"(v) : "Nd"(p)); return v; }
static void outb(u16 p, u8 v) { __asm__ volatile("outb %0,%1" : : "a"(v), "Nd"(p)); }

static void cursor(void) {
    u16 pos = cy * COLS + cx;
    outb(0x3D4, 14); outb(0x3D5, pos >> 8);
    outb(0x3D4, 15); outb(0x3D5, pos & 0xFF);
}

static void clear(void) {
    for (int i = 0; i < COLS * ROWS; i++) VGA[i] = (color << 8) | ' ';
    cx = cy = 0;
    cursor();
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
static const char keymap_sh[128] = {
    0, 27, '!','@','#','$','%','^','&','*','(',')','_','+','\b',
    '\t','Q','W','E','R','T','Y','U','I','O','P','{','}','\n',
    0,'A','S','D','F','G','H','J','K','L',':','"','~',
    0,'|','Z','X','C','V','B','N','M','<','>','?',0,'*',0,' '
};

static char getc(void) {
    static int shift;
    for (;;) {
        while (!(inb(0x64) & 1)) ;
        u8 sc = inb(0x60);
        if (sc == 0x2A || sc == 0x36) { shift = 1; continue; }
        if (sc == 0xAA || sc == 0xB6) { shift = 0; continue; }
        if (sc & 0x80) continue;
        char c = shift ? keymap_sh[sc] : keymap[sc];
        if (c) return c;
    }
}

static void reboot(void) {
    while (inb(0x64) & 2) ;
    outb(0x64, 0xFE);
}

static void halt(void) {
    /* QEMU ACPI poweroff */
    __asm__ volatile("outw %0,%1" : : "a"((u16)0x2000), "Nd"((u16)0x604));
    for (;;) __asm__ volatile("cli; hlt");
}

static void cmd(const char *l) {
    if (!*l) return;
    if (streq(l, "help")) puts("Commands: help clear about color reboot halt\n");
    else if (streq(l, "clear")) clear();
    else if (streq(l, "about")) puts("MiniOS: 32-bit protected-mode kernel, VGA text, polled keyboard.\n");
    else if (streq(l, "color")) { color = (color & 0x0F) == 0x0F ? 0x0A : 0x0F; puts("Color changed.\n"); }
    else if (streq(l, "reboot")) reboot();
    else if (streq(l, "halt")) halt();
    else { puts("Unknown command: "); puts(l); putc('\n'); }
}

void kmain(void) {
    char line[80]; int n;
    clear();
    puts("MiniOS v0.1\nType 'help' for commands.\n\n");
    for (;;) {
        puts("> ");
        n = 0;
        for (;;) {
            char c = getc();
            if (c == '\n') { putc('\n'); break; }
            if (c == '\b') { if (n) { n--; putc('\b'); } }
            else if (c >= ' ' && n < 78) { line[n++] = c; putc(c); }
        }
        line[n] = 0;
        cmd(line);
    }
}
