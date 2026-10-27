; HOOK1C.COM -- a resident program that takes INT 1Ch above whatever holds it, and chains it.
;
; WHY IT EXISTS. It hides a resident input stub behind INT 1Ch, the case `guest/scry.asm`'s
; already-resident check answers by asking IRQ 4's vector too; the matrix's P section loads it
; between two copies. It says so on E9 and stays resident.
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
