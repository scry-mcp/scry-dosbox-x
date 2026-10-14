; A guest with known answers for the code tools: `disassemble`, the instruction a stop
; carries, and `call_stack`.
;
; WHY IT EXISTS. A decoder is only as good as the bytes it was checked against, and a call
; stack only as good as the frames it was walked through. The probe guest has two leaf calls
; and no frame; the benches are somebody else's code, whose every byte has to be believed
; rather than known. Here the assembler's own listing is the referee: every address, every
; byte and every frame below is this file's arithmetic, and neither the emulator's code pane
; nor the host's decoder gets a vote on what they are.
;
; HOW A CALLER WALKS IT. Started with `break_on_int3=True`, it stops twice:
;
;   1. at the top, BP zeroed and nothing on the stack but DOS's return word: the stop with
;      no frame, where a call stack has only its own row;
;   2. in `inner`, three calls deep: `start` -> `outer` (an indirect near call through a
;      word), `outer` -> `middle` (a far call through a far pointer whose segment is filled
;      from CS at run time, so `middle` ends in `retf`), `middle` -> `inner` (a direct near
;      call). `outer` and `inner` build the C frame (`push bp`, `mov bp, sp`), `middle` the
;      186's `enter`, which is the frame Borland's compilers emit.
;
; EACH ROUTINE SAYS IT ARRIVED, on port E9: `CODE . enter outer`, then `middle`, then
; `inner`. That log is the account the walked stack is held against, and it comes from the
; guest, not from anything the tools read.
;
; BETWEEN THE TWO STOPS IT RUNS 386 CODE IN THIS 16-BIT SEGMENT, operand and address size
; prefixes and a scaled index, because a 16-bit decoder that ignores `66h`/`67h` reads every
; byte after them wrong, and DOS programs built with a 386 in mind are full of them.
;
; AND AFTER THE PARKING `jmp`, AN INSTRUCTION NO X86 HAS: `FE` with a ModRM whose reg field
; is 7 has none in any generation. Never executed, it is there so a decoder has to admit it
; knows no such instruction, rather than invent one, and go on at the next byte. The
; emulator's code pane disagrees on purpose, and it is right about its own machine: DOSBox
; runs its BIOS and DOS in C++, and the guest reaches them through `FE 38 nn nn`, an opcode
; the real chip never had, so its disassembler reads any `FE /7` as `callback` with a word
; after it. The two NOPs fill that word, so both readings
; end at the same byte and the rest of the listing lines up again.
;
; ITS CONF RUNS IT AND NOTHING ELSE: `code.conf` mounts this directory, opens port E9 and
; runs `CODE.COM`, which never exits.

        cpu     386
        org     0x100

start:  xor     bp, bp                  ; a frame chain ends at a zero BP, as C's does
        int     3                       ; stop 1: no frame
known:  mov     ax, 0x1234
        mov     [word_v], ax            ; a direct memory operand on a data label
        add     word [word_v], 5
        mov     bx, word_v
        mov     cx, [bx+2]              ; register-relative: no name can be claimed for it
        xor     ebx, ebx                ; 66h: the 386 block, in a 16-bit segment
        mov     eax, 0x12345678
        mov     [dword_v], eax
        mov     ecx, [ebx*4+dword_v]    ; 67h and 66h: a scaled index, a 32-bit displacement
        add     ecx, 0x00100000
        mov     [ptr_middle+2], cs      ; the far pointer's segment is wherever DOS put us
        call    [ptr_outer]             ; an indirect near call through a word
park:   jmp     park
        db      0xFE, 0xF8              ; FE /7: no instruction, never reached
        nop                             ; the word the pane's `callback` reads
        nop

outer:  push    bp
        mov     bp, sp
        mov     si, s_outer
        call    emit
        call    far [ptr_middle]        ; a far call through a far pointer
        pop     bp
        ret

middle: enter   4, 0
        mov     si, s_middle
        call    emit
        call    inner                   ; a direct near call
        leave
        retf

inner:  push    bp
        mov     bp, sp
        mov     si, s_inner
        call    emit
        int     3                       ; stop 2: three frames deep
        pop     bp
        ret

; --- write the NUL-terminated string at SI to port 0xE9 ---------------------------------
emit:   lodsb
        test    al, al
        jz      .done
        out     0xE9, al
        jmp     emit
.done:  ret

word_v: dw      0, 0x5678
dword_v:dd      0
ptr_outer:dw    outer
ptr_middle:dw   middle, 0
s_outer:db      "CODE . enter outer", 13, 10, 0
s_middle:db     "CODE . enter middle", 13, 10, 0
s_inner:db      "CODE . enter inner", 13, 10, 0
