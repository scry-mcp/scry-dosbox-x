; A guest with known answers for the watches that record without stopping: what was written
; where, by which instruction, and read how often.
;
; WHY IT EXISTS. A row that says "written 5 by 0814:0123" is only worth something if 5 and
; 0814:0123 are known before the row is read. Here they are this file's arithmetic: once per
; BIOS tick the loop increments `count` (one byte, at `w_inc`), copies it into the low byte of
; `pair` as a word (at `w_pair`, so the trigger's neighbour is written too), and reads `polled`
; once (at `r_poll`). Every write `count` takes is one more than the last, starting at 1, and
; a capture of it holds, in its block, the value from before the write: one less.
;
; HOW A CALLER WALKS IT. Started with `break_on_int3=True`, it stops at the top before any of
; it, where the watches are declared; released, it runs the loop forever. It says
; `TAP . loop` on E9 once, as it enters the loop.

        cpu     386
        org     0x100

start:  int     3                       ; the stop where the watches go in
        mov     si, s_loop
        call    emit
        mov     es, [zero]
        mov     bl, [es:0x46C]          ; the BIOS tick count's low byte
tick:   cmp     bl, [es:0x46C]
        je      tick
        mov     bl, [es:0x46C]
w_inc:  inc     byte [count]            ; the trigger: one write a tick, one more each time
        movzx   ax, byte [count]
w_pair: mov     [pair], ax              ; a word whose low byte is the count's copy
r_poll: mov     al, [polled]            ; one read a tick
        jmp     tick

; --- write the NUL-terminated string at SI to port 0xE9 ---------------------------------
emit:   lodsb
        test    al, al
        jz      .done
        out     0xE9, al
        jmp     emit
.done:  ret

        align   4
count:  db      0
        db      0xA5, 0x5A, 0xC3        ; the rest of count's dword: a block holds them unchanged
pair:   dw      0
polled: db      0x42
zero:   dw      0
s_loop: db      "TAP . loop", 13, 10, 0
