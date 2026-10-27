; MICKEYS.COM -- the live tier's motion guest: what a program that reads MOTION, not position,
; sees of the mouse.
;
; Run bare it asks the DOS driver for its motion counters (INT 33h AX=0Bh) and counts the driver's
; movement events through a handler of its own (AX=0Ch, mask 1), the two ways a game reads a mouse
; without asking where the pointer is; each time either moves it writes
; `MICKEY . counters dx=<n> dy=<n> events=<n>`, the counters summed since it began. Run as
; `MICKEYS.COM P` it drives the PS/2 mouse through the BIOS instead (INT 15h C2h), the way a
; program with no driver does, and writes `MICKEY . ps2 dx=<n> dy=<n> events=<n>` summed from its
; packets, each one an event. Once set up it writes `MICKEY . ready counters` or
; `MICKEY . ready ps2`, or `MICKEY . ps2 refused ah=<n>` when the BIOS turns the device down. It
; never returns. Built here from this source, like the other guests:
;
;     nasm -f bin mickeys.asm -o mickeys.com
        org 100h
        cpu 386
        mov     al, [80h]           ; the command tail's length
        or      al, al
        jz      counters
        mov     si, 81h
.tail:  lodsb
        cmp     al, 'P'
        je      ps2
        cmp     al, 0Dh
        jne     .tail

counters:
        xor     ax, ax
        int     33h
        mov     ax, 0Ch
        mov     cx, 1               ; the movement event only
        push    cs
        pop     es
        mov     dx, on_move
        int     33h
        mov     dx, m_ready_c
        call    pr
        call    nl
.loop:  mov     ax, 0Bh
        int     33h                 ; cx, dx = motion since the last call
        add     [tx], cx
        add     [ty], dx
        mov     ax, [events]
        cmp     ax, [shown]
        jne     .show
        or      cx, dx
        jz      .loop
.show:  mov     ax, [events]
        mov     [shown], ax
        mov     dx, m_counters
        call    totals
        jmp     .loop

on_move:                            ; the driver's far call, on its own stack and segments
        inc     word [cs:events]
        retf

ps2:
        mov     ax, 0C205h
        mov     bh, 3               ; three-byte packets
        int     15h
        jc      .refused
        push    cs
        pop     es
        mov     bx, on_packet
        mov     ax, 0C207h
        int     15h
        jc      .refused
        mov     ax, 0C200h
        mov     bh, 1               ; enable
        int     15h
        jc      .refused
        mov     dx, m_ready_p
        call    pr
        call    nl
.loop:  mov     ax, [events]
        cmp     ax, [shown]
        je      .loop
        mov     [shown], ax
        mov     dx, m_ps2
        call    totals
        jmp     .loop
.refused:
        push    ax
        mov     dx, m_refused
        call    pr
        pop     ax
        mov     al, ah
        xor     ah, ah
        call    sdec
        call    nl
.halt:  jmp     .halt

; The BIOS's far call per packet: status, X, Y and a zero pushed before it, in that order.
on_packet:
        push    bp
        mov     bp, sp
        push    ax
        push    bx
        mov     ax, [bp+12]         ; status: bit 4 X negative, bit 5 Y negative
        mov     bx, [bp+10]
        xor     bh, bh
        test    al, 10h
        jz      .x
        mov     bh, 0FFh
.x:     add     [cs:tx], bx
        mov     bx, [bp+8]
        xor     bh, bh
        test    al, 20h
        jz      .y
        mov     bh, 0FFh
.y:     add     [cs:ty], bx
        inc     word [cs:events]
        pop     bx
        pop     ax
        pop     bp
        retf

; ds:dx = the line's head; then the sums and the count.
totals:
        call    pr
        mov     dx, m_dx
        call    pr
        mov     ax, [tx]
        call    sdec
        mov     dx, m_dy
        call    pr
        mov     ax, [ty]
        call    sdec
        mov     dx, m_n
        call    pr
        mov     ax, [events]
        call    sdec
        call    nl
        ret

sdec:                               ; ax signed -> decimal on E9
        test    ax, ax
        jns     .pos
        push    ax
        mov     al, '-'
        out     0E9h, al
        pop     ax
        neg     ax
.pos:   xor     cx, cx
        mov     bx, 10
.d1:    xor     dx, dx
        div     bx
        push    dx
        inc     cx
        test    ax, ax
        jnz     .d1
.d2:    pop     ax
        add     al, '0'
        out     0E9h, al
        loop    .d2
        ret

pr:                                 ; ds:dx = '$'-terminated, to E9
        mov     si, dx
.c:     lodsb
        cmp     al, '$'
        je      .e
        out     0E9h, al
        jmp     .c
.e:     ret

nl:     mov     al, 13
        out     0E9h, al
        mov     al, 10
        out     0E9h, al
        ret

m_ready_c   db 'MICKEY . ready counters$'
m_ready_p   db 'MICKEY . ready ps2$'
m_refused   db 'MICKEY . ps2 refused ah=$'
m_counters  db 'MICKEY . counters$'
m_ps2       db 'MICKEY . ps2$'
m_dx        db ' dx=$'
m_dy        db ' dy=$'
m_n         db ' events=$'
tx          dw 0
ty          dw 0
events      dw 0
shown       dw 0
