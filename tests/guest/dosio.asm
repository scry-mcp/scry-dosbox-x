; A guest with known answers for the machine tools and the DOS channels: what DOS was asked, what
; it answered, which file the guest left, and a counter only the timer interrupt moves.
;
; WHY IT EXISTS. A traced call that says "open MISSING.TXT, carry set, error 2" is only worth
; something if the open, the name and the error are known before the trace is read; a frozen
; byte only proves anything if something keeps trying to change it; a masked IRQ 0 only proves
; anything if a counter that IRQ 0 alone moves stops moving. Here all of it is this file's:
;
;   - `on_tick` takes INT 8 and increments `ticks` once per timer interrupt, then chains to
;     the handler it displaced, so the BIOS clock still runs. Nothing else writes `ticks`.
;   - At `dos_calls` it opens IN.TXT and reads 4 bytes (`SCRY`), closes it, then opens
;     MISSING.TXT, which is never there: DOS answers carry set and AX 2, file not found.
;   - The first letter of its command tail decides the file it leaves: `W` creates OUT.TXT and
;     writes `SCRY` into it, `E` creates it and writes nothing, anything else leaves it alone.
;     Those are the guest file channel's `written`, `empty` and, with no OUT.TXT there or one
;     left from an earlier run, `absent` and `unchanged`.
;
; HOW A CALLER WALKS IT. Started with `break_on_int3=True`, it stops at the top before any of
; it, where watches go in; released, it makes its DOS calls, says `DOSIO . done` on E9, and
; waits for interrupts forever.
;
;     nasm -f bin dosio.asm -o dosio.com

        cpu     386
        org     0x100

start:  int     3                       ; the stop where the declarations go in
        mov     ax, 0x3508
        int     0x21
        mov     [old8], bx
        mov     [old8+2], es
        mov     ax, 0x2508
        mov     dx, on_tick
        int     0x21

dos_calls:
        mov     ax, 0x3D00              ; open IN.TXT for reading
        mov     dx, n_in
        int     0x21
        jc      .missing
        mov     bx, ax
        mov     ah, 0x3F                ; read 4 bytes
        mov     cx, 4
        mov     dx, buffer
        int     0x21
        mov     ah, 0x3E                ; close
        int     0x21
.missing:
        mov     ax, 0x3D00              ; open MISSING.TXT: carry set, AX 2
        mov     dx, n_missing
        int     0x21

        cmp     byte [0x80], 2          ; no tail, or a space alone: leave the file alone
        jb      .said
        mov     al, [0x82]              ; the tail's first letter, after its leading space
        and     al, 0xDF                ; upper case
        cmp     al, 'W'
        je      .create
        cmp     al, 'E'
        jne     .said
.create:
        push    ax
        mov     ah, 0x3C                ; create OUT.TXT
        xor     cx, cx
        mov     dx, n_out
        int     0x21
        pop     dx
        jc      .said
        mov     bx, ax
        xor     cx, cx                  ; `E` writes nothing
        cmp     dl, 'W'
        jne     .close
        mov     cx, 4
.close: mov     ah, 0x40
        mov     dx, buffer
        int     0x21
        mov     ah, 0x3E
        int     0x21

.said:  mov     si, s_done
        call    emit
idle:   sti
        hlt
        jmp     idle

on_tick:
        inc     byte [cs:ticks]         ; the only writer of `ticks`
        jmp     far [cs:old8]

; --- write the NUL-terminated string at SI to port 0xE9 ---------------------------------
emit:   lodsb
        test    al, al
        jz      .done
        out     0xE9, al
        jmp     emit
.done:  ret

ticks:  db      0
old8:   dd      0
buffer: db      "SCRY"
n_in:   db      "IN.TXT", 0
n_missing: db   "MISSING.TXT", 0
n_out:  db      "OUT.TXT", 0
s_done: db      "DOSIO . done", 13, 10, 0
