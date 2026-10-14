; INJECT.COM -- the guest half of the driver's serial input route.
;
; WHY THIS EXISTS. A DOS program running under DOSBox-X can be sent keystrokes from the host
; in two ways this package has measured. The window route posts a host key event to the
; emulator's frontmost window: it needs a window, borrows the focus, and needs the
; Accessibility grant. This route needs none of that: DOSBox-X's own INTEGRATION DEVICE
; (`integration device=true`, in the `[cpu]` section) exposes an 8042 injection register
; that only GUEST code can write, and the serial port, as `serial1=nullmodem port:N`, is a
; TCP socket the host connects to. This tiny resident program joins the two: on every timer
; tick (INT 1Ch, 18.2 Hz) it drains whatever bytes arrived on COM1 and writes each one into
; the injection register as a scan byte. The host composes the whole scan sequence -- make
; codes, break codes, an E0 prefix for an extended key -- so the stub knows nothing about
; keys and never has to; it is a byte pump. It is what the upstream maintainer suggested in
; issue #4601 while a first-class control channel does not exist.
;
; ONE BYTE PER TICK, and that is measured rather than tidy: the emulated 8042 holds one byte,
; and a make written back to back with its break lost the make (upstream's own injector
; spaces them 100 ms apart). A tick apart they arrive whole.
;
; PORT I/O ONLY inside the tick handler, so it is safe from an interrupt: no DOS call, no
; stack it does not own, nothing reentrant.
;
; It announces itself on the E9 port (`STUB  . inject device=present|absent`) so a host
; reading the log can tell whether the device answered before it trusts the route. A build
; whose device does not answer exits with a code and stays out of memory.
;
; Protocol (upstream include/iglib.h): index port = base+0, data = base+1, command = base+2;
; a register select is a RESET_LATCH command then four byte writes to the index port LSB
; first; a data write is a RESET_LATCH then four byte writes to the data port LSB first.
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
        ; THE FIFO IS ON. Without it the UART holds one received byte, and a make and its
        ; break arriving in one burst overran it: the emulator's own log said
        ; `Overrun RX:1` and the key never came. With the FIFO the burst queues and the
        ; tick drains it a byte at a time, which is the pace the 8042 wants anyway.
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
tick:
        pushf
        call    far [cs:old1c]
        push    eax
        push    ecx
        push    dx
        mov     dx, COM1+5          ; LSR
        in      al, dx
        test    al, 1               ; data ready?
        jz      .done
        mov     dx, COM1            ; RBR
        in      al, dx
        call    inject_byte
.done:
        pop     dx
        pop     ecx
        pop     eax
        iret

; al = one scan byte, written into the injection register verbatim.
inject_byte:
        push    eax
        movzx   eax, al
        push    eax
        mov     eax, REG_KB_INJECT
        call    write_regsel
        pop     eax
        call    write_data
        pop     eax
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
msg_present db 'STUB  . inject device=present', 13, 10, '$'
msg_absent  db 'STUB  . inject device=absent', 13, 10, '$'
resident_end:
