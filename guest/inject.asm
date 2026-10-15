; INJECT.COM -- the guest half of the server's input route: keys, mouse buttons, the pointer.
;
; WHAT IT JOINS. DOSBox-X's own INTEGRATION DEVICE (`integration device=true`, in the `[cpu]`
; section) exposes registers that only GUEST code can write, and the serial port, as
; `serial1=nullmodem port:N`, is a TCP socket the host connects to. Between the two, a host can
; press keys and buttons and place the pointer with no host event at all: nothing takes the
; owner's focus or moves their pointer, and the window's scale changes nothing. This resident program joins the two: on every timer tick (INT 1Ch, 18.2 Hz) it
; takes ONE COMMAND off COM1 and carries it out inside the machine. It is what the upstream
; maintainer suggested in issue #4601 while a first-class control channel does not exist.
;
; THE COMMANDS (protocol 2), each an opcode byte and a fixed payload:
;   'K' b              a scan byte into the 8042 keyboard register (the host composes makes,
;                      breaks and E0 prefixes, so the stub knows nothing about keys)
;   'B' b              a mouse button into the same register's button sub-selector: bit 7
;                      pressed or released, the low bits which button (0 left, 1 right, 2 middle)
;   'M' xl xh yl yh    INT 33h AX=04h: the pointer AT these driver coordinates, exactly
;   'R'                report on E9: INT 33h AX=03h (position, buttons), AX=26h (the driver's
;                      range), the BIOS video mode, the display size
;   'S'                a screenshot, through the device's capture trigger
; An unknown opcode is dropped, so a host speaking a newer protocol cannot wedge the stub.
;
; ONE COMMAND PER TICK, and that is measured rather than tidy: the emulated 8042 holds one
; byte, and a make written back to back with its break lost the make (upstream's own injector
; spaces them 100 ms apart). A tick apart they arrive whole. A button or a position goes
; through the same queue, so a click's press and release keep their order with the keys'.
;
; THE POINTER IS SET (AX=04h) and read back (AX=03h), never moved by a delta: the server's
; REFERENCE says why. Calling INT 33h from a timer handler is sound against DOSBox-X's own driver, which is
; emulator code behind a callback; a mouse driver loaded INSIDE the guest is not reached by
; this route and is not supported.
;
; It announces itself on the E9 port (`STUB  . inject device=present proto=2`) so a host
; reading the log can tell whether the device answered, and which protocol it speaks, before
; it trusts the route. A build whose device does not answer exits with a code and stays out
; of memory.
;
; Device protocol (upstream include/iglib.h): index port = base+0, data = base+1, command =
; base+2; a register select is a RESET_LATCH command then four byte writes to the index port
; LSB first; a data write is a RESET_LATCH then four byte writes to the data port LSB first.
; The base port is 0x28.
;
; Build: nasm -f bin inject.asm -o INJECT.COM

        org 100h
        cpu 386

BASE    equ 28h
IDX     equ BASE+0
DAT     equ BASE+1
CMD     equ BASE+2
CMD_RESET_LATCH  equ 00h
REG_IDENTIFY     equ 00000000h
ID_MAGIC         equ 0D05B0740h
REG_KB_INJECT    equ 00804200h      ; sub-selector KB is 0 << 8: the low byte is the scan byte
INJECT_MOUSEBTN  equ 0800h          ; sub-selector 8: bit 7 press, low bits the button
REG_VGA_SIZE     equ 006845C0h      ; height << 16 | width, as the display draws it
REG_SCREENSHOT   equ 00C54010h      ; bit 0: take a screenshot
BIOS_VIDEO_MODE  equ 0449h          ; the BIOS data area's current mode byte (segment 0)
COM1             equ 3F8h

start:
        ; --- probe: does the device answer? ---
        mov     eax, REG_IDENTIFY
        call    write_regsel
        call    read_data           ; eax = identification
        cmp     eax, ID_MAGIC
        je      .present
        mov     dx, msg_absent
        call    e9_print
        mov     ax, 4C01h
        int     21h
.present:
        ; ALREADY RESIDENT? A second copy would drain the same COM1 and split every command
        ; between two parsers, so a conf that runs the stub AND a server that loads it before
        ; a `program` must end with one. Asked before the UART is touched, so the resident
        ; copy's queue is left alone. The handler is preceded by a signature, so the INT 1Ch
        ; vector itself says whose it is.
        mov     ax, 351Ch
        int     21h                 ; es:bx = the current vector
        cld
        cmp     bx, SIG_LEN
        jb      .first
        mov     di, bx
        sub     di, SIG_LEN
        mov     si, signature
        mov     cx, SIG_LEN
        repe    cmpsb               ; ds:si (ours) against es:di (the vector's owner)
        jne     .first
        mov     dx, msg_twice
        call    e9_print
        mov     ax, 4C00h
        int     21h
.first:
        mov     dx, msg_present
        call    e9_print
        ; --- the UART: 8N1, divisor 1, no interrupts; the tick handler polls it ---
        mov     dx, COM1+3
        mov     al, 80h             ; DLAB on
        out     dx, al
        mov     dx, COM1
        mov     al, 1               ; divisor low
        out     dx, al
        mov     dx, COM1+1
        xor     al, al              ; divisor high
        out     dx, al
        mov     dx, COM1+3
        mov     al, 03h             ; 8N1, DLAB off
        out     dx, al
        mov     dx, COM1+1
        xor     al, al              ; no UART interrupts
        out     dx, al
        ; THE FIFO IS ON: a make and its break arriving in one burst would otherwise overrun the
        ; one-byte receiver, and the tick drains the queue a byte at a time anyway.
        mov     dx, COM1+2
        mov     al, 07h             ; FCR: enable FIFO, clear both
        out     dx, al
        mov     dx, COM1+4
        mov     al, 03h             ; DTR + RTS
        out     dx, al
        ; --- hook INT 1Ch and stay resident ---
        mov     ax, 351Ch
        int     21h                 ; es:bx = old vector
        mov     [old1c], bx
        mov     [old1c+2], es
        mov     ax, 251Ch
        mov     dx, tick
        int     21h
        mov     dx, (resident_end - start + 100h + 15) / 16
        mov     ax, 3100h
        int     21h                 ; TSR

; ---------------------------------------------------------------- the tick handler
; Bytes are taken off the UART until one command is whole (or the UART is empty: the rest of
; the command waits in `buf` for the next tick), then that one command runs.
signature db 'SCRY-INJECT-2'      ; what the already-resident check reads before `tick`
SIG_LEN equ $ - signature
tick:
        pushf
        call    far [cs:old1c]
        pushad
        push    ds
        push    es
        push    cs
        pop     ds
        cld                         ; the interrupted program's direction flag is not ours
.more:
        mov     dx, COM1+5
        in      al, dx
        test    al, 1
        jz      .done
        mov     dx, COM1
        in      al, dx
        movzx   bx, byte [have]
        mov     [buf+bx], al
        inc     byte [have]
        ; how long is this command?
        mov     al, [buf]
        mov     cl, 2
        cmp     al, 'K'
        je      .len
        cmp     al, 'B'
        je      .len
        mov     cl, 5
        cmp     al, 'M'
        je      .len
        mov     cl, 1
.len:
        cmp     [have], cl
        jb      .more
        mov     byte [have], 0
        mov     al, [buf]
        cmp     al, 'K'
        jne     .notk
        mov     al, [buf+1]
        call    inject_byte
        jmp     .done
.notk:  cmp     al, 'B'
        jne     .notb
        movzx   eax, byte [buf+1]
        or      eax, INJECT_MOUSEBTN
        call    inject_reg
        jmp     .done
.notb:  cmp     al, 'M'
        jne     .notm
        mov     ax, 4
        mov     cx, [buf+1]
        mov     dx, [buf+3]
        int     33h
        jmp     .done
.notm:  cmp     al, 'R'
        jne     .notr
        call    report
        jmp     .done
.notr:  cmp     al, 'S'
        jne     .done               ; unknown opcode: dropped
        mov     eax, REG_SCREENSHOT
        call    write_regsel
        mov     eax, 1
        call    write_data
.done:
        pop     es
        pop     ds
        popad
        iret

report:
        mov     dx, msg_rep
        call    e9_print
        mov     ax, 3
        int     33h
        push    bx
        push    dx
        mov     ax, cx
        call    e9_dec
        mov     dx, msg_y
        call    e9_print
        pop     ax
        call    e9_dec
        mov     dx, msg_b
        call    e9_print
        pop     ax
        call    e9_dec
        mov     dx, msg_max
        call    e9_print
        mov     ax, 26h
        int     33h
        push    dx
        mov     ax, cx
        call    e9_dec
        mov     al, ','
        call    e9_char
        pop     ax
        call    e9_dec
        mov     dx, msg_mode
        call    e9_print
        xor     ax, ax
        mov     es, ax
        movzx   ax, byte [es:BIOS_VIDEO_MODE]
        call    e9_dec
        mov     dx, msg_scr
        call    e9_print
        mov     eax, REG_VGA_SIZE
        call    write_regsel
        call    read_data
        push    eax
        call    e9_dec
        mov     al, 'x'
        call    e9_char
        pop     eax
        shr     eax, 16
        call    e9_dec
        mov     al, 13
        call    e9_char
        mov     al, 10
        call    e9_char
        ret

e9_dec:                             ; ax unsigned -> decimal on E9
        push    bx
        push    cx
        push    dx
        xor     cx, cx
        mov     bx, 10
.d1:    xor     dx, dx
        div     bx
        push    dx
        inc     cx
        test    ax, ax
        jnz     .d1
.d2:    pop     ax
        add     al, '0'
        call    e9_char
        loop    .d2
        pop     dx
        pop     cx
        pop     bx
        ret

; al = one scan byte, written into the injection register verbatim.
inject_byte:
        movzx   eax, al
inject_reg:                         ; eax = value for the 8042 inject register
        push    eax
        mov     eax, REG_KB_INJECT
        call    write_regsel
        pop     eax
        call    write_data
        ret

; ---------------------------------------------------------------- device I/O
write_regsel:                       ; eax = register
        push    eax
        mov     al, CMD_RESET_LATCH
        mov     dx, CMD
        out     dx, al
        pop     eax
        mov     dx, IDX
        call    out4
        ret

write_data:                         ; eax = value
        push    eax
        mov     al, CMD_RESET_LATCH
        mov     dx, CMD
        out     dx, al
        pop     eax
        mov     dx, DAT
        call    out4
        ret

read_data:                          ; -> eax
        mov     al, CMD_RESET_LATCH
        mov     dx, CMD
        out     dx, al
        mov     dx, DAT
        in      al, dx
        movzx   eax, al
        push    eax
        in      al, dx
        movzx   eax, al
        shl     eax, 8
        pop     ecx
        or      ecx, eax
        in      al, dx
        movzx   eax, al
        shl     eax, 16
        or      ecx, eax
        in      al, dx
        movzx   eax, al
        shl     eax, 24
        or      eax, ecx
        ret

out4:                               ; eax -> port dx, LSB first
        out     dx, al
        shr     eax, 8
        out     dx, al
        shr     eax, 8
        out     dx, al
        shr     eax, 8
        out     dx, al
        ret

; ---------------------------------------------------------------- E9 output
e9_print:                           ; ds:dx = '$'-terminated
        push    si
        mov     si, dx
.next:  lodsb
        cmp     al, '$'
        je      .end
        call    e9_char
        jmp     .next
.end:   pop     si
        ret

e9_char:                            ; al
        push    dx
        mov     dx, 0E9h
        out     dx, al
        pop     dx
        ret

; ---------------------------------------------------------------- data
old1c       dd 0
; No timestamp: a stamp is the guest program's own clock, and this is not the program.
msg_present db 'STUB  . inject device=present proto=2', 13, 10, '$'
msg_rep db 'STUB  . mouse x=$'
msg_y db ' y=$'
msg_b db ' buttons=$'
msg_max db ' max=$'
msg_mode db ' mode=$'
msg_scr db ' screen=$'
have db 0            ; bytes of the current command taken so far
buf times 8 db 0      ; the current command, opcode first
msg_absent  db 'STUB  . inject device=absent', 13, 10, '$'
msg_twice   db 'STUB  . inject already resident', 13, 10, '$'
resident_end:
