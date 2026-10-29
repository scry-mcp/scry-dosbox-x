; STACK.COM -- how deep the input stub reaches into the interrupted program's own stack.
;
; It puts itself on a private stack inside its segment, fills the stack with 0CCh after the DOS
; mouse driver is up, writes `STACK . ready` on E9 and idles in HLT. The stub's entries (IRQ 4, the
; timer tick) run on that stack; the host sends it input and reads the stack back, and the lowest
; byte no longer 0CCh is the deepest the stub went. Built here from this source, like the other
; guests:
;
;     nasm -f bin stack.asm -o stack.com
        org 100h
        cpu 386
STACK_BYTES equ 1024
        cli
        mov     ax, cs
        mov     ss, ax
        mov     sp, stack_top
        sti
        xor     ax, ax
        int     33h                 ; the driver's reset runs on this stack too
        push    cs
        pop     es
        mov     di, stack_lo
        mov     cx, STACK_BYTES
        mov     al, 0CCh
        cld
        rep     stosb
        mov     si, m_ready
.say:   lodsb
        or      al, al
        jz      .idle
        mov     dx, 0E9h
        out     dx, al
        jmp     .say
.idle:  hlt
        jmp     .idle

m_ready db "STACK . ready", 13, 10, 0
align 16
stack_lo:
        times STACK_BYTES db 0
stack_top:
