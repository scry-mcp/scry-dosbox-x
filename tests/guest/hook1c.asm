; HOOK1C.COM -- a resident program that takes INT 1Ch above whatever holds it, and chains it.
;
; WHY IT EXISTS. The input stub knows a copy of itself is already resident by the signature in
; front of its handlers, read through their vectors. A TSR loaded after the first copy, as a
; conf's own `[autoexec]` can load one, puts its handler on INT 1Ch, and through that vector the
; first copy is out of sight: the second would install, and two parsers would split COM1. The
; matrix's P section loads this between the two copies. It says so on E9 and stays resident.
;
;     nasm -f bin hook1c.asm -o hook1c.com
        org 100h
        mov     ax, 351Ch
        int     21h
        mov     [old], bx
        mov     [old+2], es
        mov     ax, 251Ch
        mov     dx, tick
        int     21h
        mov     si, m_hooked
.say:   lodsb
        cmp     al, '$'
        je      .stay
        out     0E9h, al
        jmp     .say
.stay:  mov     dx, (resident_end - $$ + 100h + 15) / 16
        mov     ax, 3100h
        int     21h
tick:   jmp     far [cs:old]
old     dd 0
resident_end:
m_hooked db "HOOK1C . int 1Ch hooked", 13, 10, "$"
