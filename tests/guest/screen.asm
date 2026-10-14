; A guest with known answers for the screen tools, so a decoder is proven exact.
;
; WHY IT EXISTS. The screen tools read video memory and the VGA's registers at a stop and turn
; them into text, a picture or a number. Checked against a program somebody else wrote, the
; only reference is that program's screen as the emulator renders it, and none of the benches
; this package runs draws in mode 13h or writes the DAC on purpose. So this guest draws things
; whose every byte is its own arithmetic, and the tests compare against that arithmetic, never
; against a value read back from the emulator.
;
; HOW A CALLER WALKS IT. Each step ends in `int 3`, and a session started with
; `break_on_int3=True` stops at the debugger there; `resume` goes on to the next. The steps:
;
;   1. text mode 3, two lines printed through DOS: the top row and the one under it.
;   2. the CRTC start address set to 80 (one text row), so the screen shows the page from
;      its second row; then back to 0 after the stop.
;   3. DAC entry 01 written to (3F, 00, 00): one palette write, every other entry untouched.
;   4. mode 13h, DAC entry i set to (i & 3F, (i >> 1) & 3F, (i >> 2) & 3F), and the window at
;      A000 filled so the pixel at (x, y) is (x + y) & FF.
;   5. the CRTC start address set to 80 in that mode, then back to 0 after the stop.
;   6. mode 12h, the planar mode, which the tools refuse: the stop is there to prove it.
;
; THE SCREEN IS LEFT TO SETTLE BEFORE EVERY STOP. The start address latches at the vertical
; retrace, and a video capture writes a frame per retrace, so each step waits for two of them
; before its `int 3`: what the registers say, what memory holds and the last captured frame
; then all describe the same picture.
;
; IT NEVER EXITS: after the last stop it spins, so a stray `resume` finds a live machine and
; not a DOS prompt redrawing the screen under the caller.
;
; ITS CONF RUNS NOTHING: `screen.conf` mounts this directory and stops at the prompt, and every
; start names `SCREEN.COM` as its `program`, which is what a `capture_video` session needs.

        cpu     8086
        org     0x100

        ; 1. text mode, two rows of known text
        mov     ax, 0x0003
        int     0x10
        mov     ah, 0x09
        mov     dx, lines
        int     0x21
        call    settle
        int     3

        ; 2. the page shown from its second row
        mov     bx, 80
        call    start_addr
        call    settle
        int     3
        xor     bx, bx
        call    start_addr

        ; 3. one DAC entry written
        mov     dx, 0x3C8
        mov     al, 0x01
        out     dx, al
        inc     dx
        mov     al, 0x3F
        out     dx, al
        xor     al, al
        out     dx, al
        out     dx, al
        call    settle
        int     3

        ; 4. mode 13h, a ramp in the DAC and a diagonal ramp on screen
        mov     ax, 0x0013
        int     0x10
        mov     dx, 0x3C8
        xor     al, al
        out     dx, al
        inc     dx
        xor     bl, bl                  ; BL is the entry; the loop ends when it wraps to 0
.dac:   mov     al, bl
        and     al, 0x3F
        out     dx, al
        mov     al, bl
        shr     al, 1
        and     al, 0x3F
        out     dx, al
        mov     al, bl
        shr     al, 1
        shr     al, 1                   ; an 8086 shifts by one or by CL, never by an immediate
        out     dx, al
        inc     bl
        jnz     .dac

        mov     ax, 0xA000
        mov     es, ax
        xor     di, di
        xor     dx, dx                  ; DX is the row
.row:   mov     al, dl                  ; the first pixel of row y is y & FF ...
        mov     cx, 320
.px:    stosb                           ; ... and each pixel to its right is one more
        inc     al
        loop    .px
        inc     dx
        cmp     dx, 200
        jb      .row
        call    settle
        int     3

        ; 5. the same picture, the display start moved
        mov     bx, 80
        call    start_addr
        call    settle
        int     3
        xor     bx, bx
        call    start_addr

        ; 6. the planar mode
        mov     ax, 0x0012
        int     0x10
        call    settle
        int     3

.spin:  jmp     .spin

; --- the CRTC start address (registers 0Ch high, 0Dh low) set to BX --------------------
start_addr:
        mov     dx, 0x3D4
        mov     al, 0x0C
        mov     ah, bh
        out     dx, ax
        mov     al, 0x0D
        mov     ah, bl
        out     dx, ax
        ret

; --- two whole vertical retraces, so the screen has been drawn as it now stands ---------
settle: call    retrace
retrace:
        mov     dx, 0x3DA
.out:   in      al, dx                  ; leave a retrace already under way ...
        test    al, 0x08
        jnz     .out
.in:    in      al, dx                  ; ... and wait for the next to begin
        test    al, 0x08
        jz      .in
        ret

lines:  db      "SCREEN GUEST: TEXT", 13, 10, "SECOND ROW", 13, 10, "$"
