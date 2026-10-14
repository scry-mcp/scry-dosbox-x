/* DPMI.EXE -- the protected-mode guest the live tier owns: a DJGPP program that runs as a DPMI
 * client under the host DOSBox-X provides, with an `nm` table, so every tool the server has for
 * a 32-bit client (selectors, a flat map, a stop by name, a watch by name, the E9 channel, keys
 * through both routes and the mouse through the window's) has something real to stand on.
 *
 * WHAT IT DOES, in the order a session meets it:
 *   - writes `BOOT  . start` on the E9 port, then reads the file named by its first argument
 *     (a path on a mounted drive) in `load_file`, called once, and says how many bytes it read;
 *   - switches to VBE mode 0x101 with its linear frame buffer (640x480, 8 bits), so the screen
 *     tools meet a mode they must refuse to read and name;
 *   - loops once per vertical retrace: `tick` bumps `g_ticks`, the counter a watch reads, and
 *     every TICK_EVERY ticks a `TICK  .` line says the input loop is up;
 *   - reads the keyboard through the BIOS's extended services (the plain ones drop F11), so a
 *     key reaches it by either route (a host key event to the window, or the serial stub's scan
 *     bytes through the 8042): every key is announced (`key down <NAME>`), `a` is answered by
 *     `key_cue_a=<ticks>`, F11 by nothing else, and alt+x asks before it quits (`right` then
 *     `enter` leaves);
 *   - reads the mouse through INT 33h and announces a button press with its position.
 *
 * Every E9 line opens with the guest's own clock, `[+SSSS.mmm]`, so a reader can cut the log
 * by seconds of the guest's time rather than of the host's.
 *
 * NOT INLINED, on purpose: `tick` and `load_file` are names a breakpoint is set on, and a call
 * to each is what a call stack walks through. The frame pointer stays for the same walk.
 *
 * Build (tests/guest/, DJDIR defaulting to $HOME/djgpp):
 *   $DJDIR/bin/i586-pc-msdosdjgpp-gcc -O1 -fno-omit-frame-pointer -Wall -Wextra -Wshadow \
 *       -Werror -o dpmi.exe dpmi.c
 *   $DJDIR/bin/i586-pc-msdosdjgpp-nm dpmi.exe > dpmi.sym
 */

#include <bios.h>
#include <dpmi.h>
#include <pc.h>
#include <stdarg.h>
#include <stdio.h>
#include <time.h>

#define E9_PORT 0xE9
#define VGA_STATUS 0x3DA
#define VGA_RETRACE 0x08
#define VBE_MODE_LIN8 0x4101 /* mode 0x101 with bit 14, the linear frame buffer */
#define TICK_EVERY 60
#define SCREEN_W 640 /* mode 0x101 */
#define SCREEN_H 480

#define KEY_A 0x1E
#define KEY_X 0x2D
#define KEY_ENTER 0x1C
#define KEY_RIGHT 0x4D
#define KEY_F11 0x85
#define SHIFT_ALT 0x08

volatile unsigned long g_ticks;
volatile long g_file_bytes;
static int asking;  /* the quit question is open */
static int choice;  /* 0 stay, 1 quit */
static int buttons; /* the mouse buttons at the last poll */

static void e9(const char *fmt, ...)
{
    char line[160];
    uclock_t now = uclock();
    unsigned long ms = (unsigned long)(now / (UCLOCKS_PER_SEC / 1000));
    int n = snprintf(line, sizeof line, "[+%04lu.%03lu] ", ms / 1000, ms % 1000);
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(line + n, sizeof line - n, fmt, ap);
    va_end(ap);
    for (const char *c = line; *c; c++)
        outportb(E9_PORT, *c);
    outportb(E9_PORT, '\n');
}

__attribute__((noinline)) long load_file(const char *path)
{
    FILE *f = fopen(path, "rb");
    long n = 0;
    if (f) {
        while (fgetc(f) != EOF)
            n++;
        fclose(f);
    }
    e9("FILE  . %s bytes=%ld", path, f ? n : -1L);
    return f ? n : -1L;
}

__attribute__((noinline)) void tick(void)
{
    g_ticks++;
}

static void retrace(void)
{
    while (inportb(VGA_STATUS) & VGA_RETRACE)
        ;
    while (!(inportb(VGA_STATUS) & VGA_RETRACE))
        ;
}

static void video(void)
{
    __dpmi_regs r = {0};
    r.x.ax = 0x4F02;
    r.x.bx = VBE_MODE_LIN8;
    __dpmi_int(0x10, &r);
    e9("VIDEO . vbe=%04X", r.x.ax);
}

static const char *key_name(int scan)
{
    switch (scan) {
    case KEY_A: return "A";
    case KEY_X: return "X";
    case KEY_ENTER: return "ENTER";
    case KEY_RIGHT: return "RIGHT";
    case KEY_F11: return "F11";
    default: return "OTHER";
    }
}

/* One key: announced, then acted on. Answers 1 when the program should leave. */
static int key(int code)
{
    int scan = (code >> 8) & 0xFF;
    int alt = bioskey(_NKEYBRD_SHIFTSTATUS) & SHIFT_ALT;
    e9("key down %s%s", alt ? "ALT+" : "", key_name(scan));
    if (asking) {
        if (scan == KEY_RIGHT)
            choice = 1;
        if (scan == KEY_ENTER) {
            e9("ask res=%d", choice);
            asking = 0;
            return choice;
        }
        return 0;
    }
    if (scan == KEY_A)
        e9("key_cue_a=%lu", g_ticks);
    if (scan == KEY_X && alt) {
        asking = 1;
        choice = 0;
        e9("ask opens");
    }
    return 0;
}

static void mouse(void)
{
    __dpmi_regs r = {0};
    r.x.ax = 0x0003;
    __dpmi_int(0x33, &r);
    int pressed = r.x.bx & ~buttons;
    buttons = r.x.bx;
    if (pressed)
        e9("mouse btn=%d x=%d y=%d", pressed, r.x.cx, r.x.dx);
}

int main(int argc, char **argv)
{
    __dpmi_regs r = {0};
    e9("BOOT  . start");
    g_file_bytes = argc > 1 ? load_file(argv[1]) : -1L;
    video();
    __dpmi_int(0x33, &r); /* AX=0: reset the mouse driver */
    /* The driver's ranges are the text screen's until told: the mode's own, so the pointer it
     * reports is a pixel of what is shown and the window's centre is the screen's. */
    r.x.ax = 0x0007, r.x.cx = 0, r.x.dx = SCREEN_W - 1;
    __dpmi_int(0x33, &r);
    r.x.ax = 0x0008, r.x.cx = 0, r.x.dx = SCREEN_H - 1;
    __dpmi_int(0x33, &r);
    for (;;) {
        retrace();
        tick();
        if (g_ticks % TICK_EVERY == 0)
            e9("TICK  . ticks=%lu", g_ticks);
        while (bioskey(_NKEYBRD_READY))
            if (key(bioskey(_NKEYBRD_READ)))
                goto leave;
        mouse();
    }
leave:
    r.x.ax = 0x0003; /* back to text mode, so the shell is readable again */
    __dpmi_int(0x10, &r);
    e9("QUIT  . ticks=%lu", g_ticks);
    return 0;
}
