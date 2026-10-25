; A guest with one instruction of each kind a step has to get right, and nothing else.
;
; WHY IT EXISTS. With the debugger driven through its channel there is no F10 or F11 key to
; press: stepping into is the `STEPIN` command, and stepping over is composed on the host (a
; breakpoint after the instruction, then `RUN`). Both are only as good as the places they land,
; and the places are this file's: the assembler's listing says where each instruction starts and
; how long it is, so a step that lands anywhere else is wrong and no emulator gets a vote.
;
; THE KINDS, in the order a caller meets them after the `int 3` stop:
;
;   mov ax, 1234h      a plain instruction: into and over land on the next one
;   call leaf          into lands on `leaf`, over on the instruction after the call
;   int 21h            DOS's own handler: into enters it, over comes back after it
;   rep movsb          one iteration per step into, all of them for a step over
;   loop again         into goes round, over leaves the loop
;   jmp parked         into and over both follow the jump
;
; IT PARKS ON A `jmp $` and never returns, so a session that stepped past the end still has a
; machine to read.
;
; Started with `break_on_int3=True`, the first `resume` stops at the `int 3`.

        org     100h

start:  int     3
        mov     ax, 1234h
        call    leaf
        mov     ah, 30h                 ; get DOS version: harmless, and a real INT 21h
        int     21h
        mov     si, source
        mov     di, target
        mov     cx, 4
        cld
        rep     movsb
        mov     cx, 3
again:  loop    again
        jmp     parked

leaf:   ret

parked: jmp     parked

source: db      "STEP"
target: times 4 db 0
