; A guest with known answers for the screen modes video memory holds in planes or past a window.
;
; WHY IT EXISTS. `screen.asm` proves the decoders that read the screen through the CPU's window
; (text, and 13h's chained bytes). The modes here cannot be read that way: a planar or an
; unchained mode answers one plane per read, and an SVGA mode's frame is larger than the 64 KB
; window the CPU sees it through. They are read from the video memory itself, so this guest
; draws in each of them a picture whose every pixel is its own arithmetic, and the tests compare
; against that arithmetic, never against a value read back from the emulator.
;
; HOW A CALLER WALKS IT. Each step ends in `int 3`, and a session started with
; `break_on_int3=True` stops at the debugger there; `resume` goes on to the next. The steps:
;
;   1. mode 12h (640 x 480, 16 colours, four planes): the pixel at (x, y) is (x + y) & 0F.
;   2. mode X (13h unchained, 320 x 200, 256 colours, pixel x in plane x & 3): (2x + y) & FF.
;   3. VBE 101h (640 x 480, 8 bits a pixel): (x ^ y) & FF.
;   4. VBE 110h (640 x 480, 15 bits a pixel): the word (y & FF) << 8 | (x & FF).
;   5. VBE 111h (640 x 480, 16 bits a pixel): the same words as step 4.
;   6. VBE 112h (640 x 480, 32 bits a pixel): the dword y << 12 | x.
;   7. VBE 102h (800 x 600, 16 colours in four planes): step 1's picture, (x + y) & 0F.
;
; The SVGA steps write through the 64 KB window at A000h, moved a bank at a time with VBE
; function 05h by the window granularity function 01h reports, so the frame is filled the way
; a DOS program of the time filled it, and nothing here needs protected mode.
;
; IT NEVER EXITS: after the last stop it spins, so a stray `resume` finds a live machine.
; Its conf is `screen.conf`: the same machine, and every start names `PLANES.COM`.

        cpu     386
        org     0x100

        ; 1. mode 12h, one plane at a time through the sequencer's map mask
        mov     ax, 0x0012
        int     0x10
        mov     word [cols], 80
        mov     word [rows], 480
        call    planar
        int     3

        ; 2. mode X: 13h, then the sequencer and the CRTC unchained
        mov     ax, 0x0013
        int     0x10
        mov     dx, 0x3C4
        mov     ax, 0x0604              ; memory mode: chain-4 off, odd/even off
        out     dx, ax
        mov     dx, 0x3D4
        mov     ax, 0x0014              ; underline location: doubleword mode off
        out     dx, ax
        mov     ax, 0xE317              ; mode control: byte mode on
        out     dx, ax
        xor     bp, bp
.planex:
        mov     dx, 0x3C4
        mov     al, 2
        mov     ah, 1
        mov     cx, bp
        shl     ah, cl
        out     dx, ax
        xor     di, di
        xor     si, si
.rowx:  xor     bx, bx                  ; BX is the column of four pixels
.quadx: mov     ax, bx                  ; x = 4 * column + plane
        shl     ax, 2
        add     ax, bp
        shl     ax, 1                   ; (2x + y) & FF
        add     ax, si
        stosb
        inc     bx
        cmp     bx, 80
        jb      .quadx
        inc     si
        cmp     si, 200
        jb      .rowx
        inc     bp
        cmp     bp, 4
        jb      .planex
        mov     dx, 0x3C4
        mov     ax, 0x0F02
        out     dx, ax
        call    settle
        int     3

        ; 3. to 6. the SVGA modes, each filled a pixel at a time through the window
        mov     word [mode], 0x0101
        mov     byte [bytes], 1
        call    svga
        int     3
        mov     word [mode], 0x0110
        mov     byte [bytes], 2
        call    svga
        int     3
        mov     word [mode], 0x0111
        call    svga
        int     3
        mov     word [mode], 0x0112
        mov     byte [bytes], 4
        call    svga
        int     3

        ; 7. VBE 102h (800 x 600, 16 colours in four planes): step 1's picture, (x + y) & 0F
        mov     ax, 0x4F02
        mov     bx, 0x0102
        int     0x10
        mov     word [cols], 100
        mov     word [rows], 600
        call    planar
        int     3

.spin:  jmp     .spin

; --- the planar picture (x + y) & 0F on [cols] bytes by [rows] rows, a plane at a time ---
planar:
        mov     ax, 0xA000
        mov     es, ax
        xor     bp, bp                  ; BP is the plane
.plane: mov     dx, 0x3C4
        mov     al, 2
        mov     ah, 1
        mov     cx, bp
        shl     ah, cl
        out     dx, ax
        xor     di, di
        xor     si, si                  ; SI is the row
.rowp: xor     bx, bx                  ; BX is the byte column
.bytep:
        mov     ax, bx                  ; the first pixel of the byte is x = 8 * column
        shl     ax, 3
        add     ax, si                  ; ... and its colour (x + y) & 0F
        mov     dl, 0                   ; DL gathers the plane's eight bits
        mov     dh, 0x80
.bitp: push    ax
        and     al, 0x0F
        mov     cx, bp
        shr     al, cl
        test    al, 1
        jz      .clear
        or      dl, dh
.clear: pop     ax
        inc     ax
        shr     dh, 1
        jnz     .bitp
        mov     [es:di], dl
        inc     di
        inc     bx
        cmp     bx, [cols]
        jb      .bytep
        inc     si
        cmp     si, [rows]
        jb      .rowp
        inc     bp
        cmp     bp, 4
        jb      .plane
        mov     dx, 0x3C4               ; every plane enabled again, as the BIOS left it
        mov     ax, 0x0F02
        out     dx, ax
        call    settle
        ret

; --- set VBE mode [mode] and draw its picture, [bytes] a pixel ---------------------------
svga:   mov     ax, 0x4F01              ; the mode's window granularity, in KB
        mov     cx, [mode]
        push    ds
        pop     es
        mov     di, info
        int     0x10
        mov     ax, 64
        xor     dx, dx
        div     word [info + 4]
        mov     [step], ax              ; banks a 64 KB window moves by
        mov     ax, 0x4F02
        mov     bx, [mode]
        int     0x10
        mov     ax, 0xA000
        mov     es, ax
        xor     ecx, ecx                ; ECX is x, EDX's high half y, through the frame
        xor     esi, esi                ; SI is y
        mov     word [bank], 0
        call    setbank
        xor     di, di
.pixel: mov     al, [bytes]
        cmp     al, 1
        je      .eight
        cmp     al, 2
        je      .word
        mov     eax, esi                ; y << 12 | x
        shl     eax, 12
        or      eax, ecx
        call    put4
        jmp     .next
.eight: mov     al, cl                  ; (x ^ y) & FF
        xor     ax, si
        call    put1
        jmp     .next
.word:  mov     ax, si                  ; (y & FF) << 8 | (x & FF)
        mov     ah, al
        mov     al, cl
        call    put1
        mov     al, ah
        call    put1
.next:  inc     ecx
        cmp     ecx, 640
        jb      .pixel
        xor     ecx, ecx
        inc     esi
        cmp     esi, 480
        jb      .pixel
        call    settle
        ret

put4:   call    put1                    ; EAX's four bytes, low first
        shr     eax, 8
        call    put1
        shr     eax, 8
        call    put1
        shr     eax, 8
        ; fall through for the last byte

; --- one byte to the window at DI, the bank moved when DI wraps -------------------------
put1:   stosb
        or      di, di
        jnz     .done
        push    eax                     ; the BIOS may use EAX's high half
        mov     ax, [bank]
        add     ax, [step]
        mov     [bank], ax
        call    setbank
        pop     eax
.done:  ret

setbank:
        push    bx
        push    dx
        mov     ax, 0x4F05
        xor     bx, bx
        mov     dx, [bank]
        int     0x10
        pop     dx
        pop     bx
        ret

; --- two whole vertical retraces, so the screen has been drawn as it now stands ---------
settle: call    retrace
retrace:
        mov     dx, 0x3DA
.out:   in      al, dx
        test    al, 0x08
        jnz     .out
.in:    in      al, dx
        test    al, 0x08
        jz      .in
        ret

name:   db      "PLANES: 12h, mode X, VBE 101h 110h 111h 112h 102h"
mode:   dw      0
cols:   dw      0
rows:   dw      0
bytes:  db      0
step:   dw      0
bank:   dw      0
info:   times 256 db 0
