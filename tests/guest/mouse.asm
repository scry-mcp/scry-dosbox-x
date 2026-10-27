; MOUSE.COM -- the live tier's mouse guest: it tells the E9 port what the DOS mouse driver says.
;
; Every time INT 33h AX=03h answers something new (the position or the buttons) it writes
; `MOUSE . pos x=<n> y=<n> b=<bits> presses=<n>`, the presses being AX=05h's count for the left
; button since the last line, so a click and a double click are both countable. A key writes
; `MOUSE . key=<ascii>`, and three keys switch the BIOS mode, so a case can try the pointer in
; another one: g -> 13h (320x200), v -> 12h (640x480), t -> 03h (text), each followed by
; `MOUSE . mode=<n>`; two more set a VBE mode, s -> 103h (800x600, 256 colours) and w -> 108h
; (80x60 text), each followed by `MOUSE . vbe=<n>`, the mode VBE then reports (4F03h). A fourth, o, takes INT 08h the way a game owns the timer: an EOI and an
; IRET, never chaining the BIOS, so INT 1Ch stops; then `MOUSE . timer=owned`. It never returns. Built here from this source, like the other guests:
;
;     nasm -f bin mouse.asm -o mouse.com
;
; IT HIDES THE TEXT CURSOR, at the start and after every mode switch (the BIOS shows it again at
; each), so its screen holds still between captures: a blinking cursor would count as part of
; the arrow in a case that compares a capture with the pointer's arrow against one without it.
        org 100h
        call    hide
        xor     ax, ax
        int     33h
        mov     dx, m_reset
        call    pr
        mov     ax, bx
        call    dec
        call    nl
loop_:
        mov     ah, 1
        int     16h
        jz      .nokey
        xor     ah, ah
        int     16h
        mov     bl, 13h
        cmp     al, 'g'
        je      .mode
        mov     bl, 12h
        cmp     al, 'v'
        je      .mode
        mov     bl, 03h
        cmp     al, 't'
        je      .mode
        mov     bx, 103h
        cmp     al, 's'
        je      .vbe
        mov     bx, 108h
        cmp     al, 'w'
        je      .vbe
        cmp     al, 'o'
        je      .own
        push    ax                  ; `pr` loads AL with each character it prints
        mov     dx, m_key
        call    pr
        pop     ax
        xor     ah, ah
        call    dec
        call    nl
        jmp     .nokey
.own:   mov     ax, 2508h
        mov     dx, own8
        int     21h
        mov     dx, m_owned
        call    pr
        call    nl
        jmp     .nokey
.mode:  xor     ah, ah
        mov     al, bl
        int     10h
        call    hide
        xor     ax, ax
        int     33h
        mov     dx, m_mode
        call    pr
        mov     ah, 0Fh             ; the mode the BIOS now holds (INT 33h's reset took BL)
        int     10h
        xor     ah, ah
        call    dec
        call    nl
        mov     word [lx], 0FFFFh
        jmp     .nokey
.vbe:   mov     ax, 4F02h
        int     10h
        call    hide
        xor     ax, ax
        int     33h
        mov     dx, m_vbe
        call    pr
        mov     ax, 4F03h
        int     10h
        mov     ax, bx
        call    dec
        call    nl
        mov     word [lx], 0FFFFh
.nokey:
        mov     ax, 3
        int     33h
        cmp     cx, [lx]
        jne     .chg
        cmp     dx, [ly]
        jne     .chg
        cmp     bx, [lb]
        je      loop_
.chg:   mov     [lx], cx
        mov     [ly], dx
        mov     [lb], bx
        push    bx
        push    dx
        mov     dx, m_pos
        call    pr
        mov     ax, cx
        call    dec
        mov     dx, m_y
        call    pr
        pop     ax
        call    dec
        mov     dx, m_b
        call    pr
        pop     ax
        call    dec
        mov     dx, m_pc
        call    pr
        mov     ax, 5
        xor     bx, bx
        int     33h
        mov     ax, bx
        call    dec
        call    nl
        jmp     loop_

own8:   push    ax
        mov     al, 20h
        out     20h, al
        pop     ax
        iret
hide:   mov     ah, 01h             ; cursor shape: start line bit 5 set hides it
        mov     cx, 2000h
        int     10h
        ret
pr:     push    si
        mov     si, dx
.n:     lodsb
        cmp     al, '$'
        je      .e
        out     0E9h, al
        jmp     .n
.e:     pop     si
        ret
nl:     mov     al, 13
        out     0E9h, al
        mov     al, 10
        out     0E9h, al
        ret
dec:    push    bx
        push    cx
        push    dx
        xor     cx, cx
        mov     bx, 10
.a:     xor     dx, dx
        div     bx
        push    dx
        inc     cx
        test    ax, ax
        jnz     .a
.b:     pop     ax
        add     al, '0'
        out     0E9h, al
        loop    .b
        pop     dx
        pop     cx
        pop     bx
        ret
lx dw 0FFFFh
ly dw 0
lb dw 0
m_reset db "MOUSE . reset buttons=$"
m_mode db "MOUSE . mode=$"
m_vbe db "MOUSE . vbe=$"
m_owned db "MOUSE . timer=owned$"
m_key db "MOUSE . key=$"
m_pos db "MOUSE . pos x=$"
m_y db " y=$"
m_b db " b=$"
m_pc db " presses=$"
