; KEYS.COM -- the live tier's keyboard timing guest: it tells the E9 port every scan byte INT 9
; takes and the BIOS tick count (0040:006C) the byte arrived at.
;
; WHY IT EXISTS. A program that reads its keys once a tick sees a make only if the break comes a
; tick later in the guest's own clock. With the emulator starved the guest's clock falls behind
; the wall's, so what the host did is read here off the guest's own tick count.
;
; EACH BYTE WRITES `KEYS . <scan hex2> t=<tick low word hex4>`. The ISR only queues the byte and
; the tick; the main loop prints, so a slow console never makes the ISR late. It never exits.
;
;     nasm -f bin keys.asm -o keys.com
        cpu     386
        org     100h
        mov     ax, 3509h
        int     21h
        mov     ax, 2509h
        mov     dx, isr
        int     21h
        mov     si, m_up
        call    emit
main:   mov     al, [tail]
        cmp     al, [head]
        je      main
        xor     bh, bh
        mov     bl, al
        mov     dl, [rb + bx]
        shl     bx, 1
        mov     cx, [rt + bx]
        mov     si, m_key
        call    emit
        mov     al, dl
        call    hex8
        mov     si, m_t
        call    emit
        mov     al, ch
        call    hex8
        mov     al, cl
        call    hex8
        mov     al, 13
        out     0E9h, al
        mov     al, 10
        out     0E9h, al
        mov     al, [tail]
        inc     al
        and     al, 31
        mov     [tail], al
        jmp     main

isr:    push    ax
        push    bx
        push    ds
        push    es
        push    cs
        pop     ds
        in      al, 60h
        mov     bl, [head]
        xor     bh, bh
        mov     [rb + bx], al
        xor     ax, ax
        mov     es, ax
        mov     ax, [es:46Ch]
        shl     bx, 1
        mov     [rt + bx], ax
        mov     al, [head]
        inc     al
        and     al, 31
        mov     [head], al
        mov     al, 20h
        out     20h, al
        pop     es
        pop     ds
        pop     bx
        pop     ax
        iret

emit:   lodsb
        test    al, al
        jz      .done
        out     0E9h, al
        jmp     emit
.done:  ret

hex8:   push    ax
        shr     al, 4
        call    nib
        pop     ax
        and     al, 0Fh
nib:    add     al, '0'
        cmp     al, '9'
        jbe     .out
        add     al, 7
.out:   out     0E9h, al
        ret

head:   db      0
tail:   db      0
rb:     times 32 db 0
rt:     times 32 dw 0
m_up:   db      "KEYS . up", 13, 10, 0
m_key:  db      "KEYS . ", 0
m_t:    db      " t=", 0
