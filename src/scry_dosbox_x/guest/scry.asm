; SCRY.COM -- the guest half of the server's input route: keys, mouse buttons, the pointer.
;
; WHAT IT JOINS. DOSBox-X's own INTEGRATION DEVICE (`integration device=true`, in the `[cpu]`
; section) exposes registers that only GUEST code can write, and the serial port, as
; `serial1=nullmodem port:N`, is a TCP socket the host connects to. Between the two, a host can
; press keys and buttons and place the pointer with no host event at all: nothing takes the
; owner's focus or moves their pointer, and the window's scale changes nothing. This resident
; program joins the two: whenever COM1 receives a byte (the UART's own interrupt, IRQ 4) it takes
; what is waiting there and carries each command out inside the machine. It is what the upstream
; maintainer suggested in issue #4601 while a first-class control channel does not exist.
;
; WHY THE UART'S INTERRUPT AND NOT THE TIMER TICK. A game commonly takes INT 08h for itself, sends
; the PIC its EOI and IRETs, never chaining the BIOS handler; from then on nothing raises INT 1Ch,
; and a stub that read COM1 only on the tick would leave every frame there unread. The serial line
; is not something a game has reason to touch. The tick (INT 1Ch)
; is still hooked, for what only a clock can do: dropping a frame left short, and draining COM1
; when a program masked IRQ 4. Both entries run one routine, never at once.
;
; A FRAME (protocol 6): SYNC (A5h), a sequence byte (1 to 255), then the command, an opcode
; byte and a fixed payload, then a CHECK: every byte after SYNC XORed into FFh. A SYNC byte can sit
; inside a payload (A5h is the break of a key), so a frame short of a byte can be completed by the
; next one's: the check is what makes that frame not add up. One that does not, or whose opcode
; is unknown, is READ AGAIN from the byte after its SYNC, because the host's resend may already
; be inside it: its SYNC went in as the short frame's tail. Every frame is ACKNOWLEDGED on COM1,
; the line it came in on: 5Ah, its sequence byte, its opcode, then 1 when it was carried out or 0
; when it was not because it
; repeats the last sequence carried out. The host sends the next frame only once the last is
; acknowledged, so the UART's queue never holds more than one frame and the guest sets the
; pace. A byte lost on the way costs one frame and runs no other, short of a misframed run whose
; one-byte check happens to add up: a frame still short after
; STALE_TICKS ticks with nothing arriving is dropped, the stub hunts for the next SYNC, and the
; host, with no acknowledgement, sends the same frame again (under a program that owns the timer
; no tick counts, the resent bytes complete the short frame wrongly, and reading its bytes again
; is what finds the resend); if it was the acknowledgement that was lost, the repeat is
; acknowledged with 0 and not carried out twice. The commands:
;   'K' b              a scan byte into the 8042 keyboard register (the host composes makes,
;                      breaks and E0 prefixes, so the stub knows nothing about keys)
;   'B' b              a mouse button into the same register's button sub-selector: bit 7
;                      pressed or released, the low bits which button (0 left, 1 right, 2 middle)
;   'M' xl xh yl yh    the pointer AT these driver coordinates, exactly (INT 33h AX=04h),
;                      reached first as motion through the device where the build takes it
;   'R'                report, on COM1 after its acknowledgement (a repeat too: it reads,
;                      it changes nothing), one line ending CR LF:
;                      INT 33h AX=03h (position, buttons), AX=26h (the driver's range), the
;                      BIOS video mode, the display size, then VBE's own word on the mode
;                      (INT 10h 4F03h; for a mode from 100h up, 4F01h's ModeAttributes and
;                      resolution). On COM1, never on E9: the program's own lines go to E9,
;                      and a report there could split one of them.
;   'S'                a screenshot, through the device's capture trigger
; An unknown opcode is never carried out, so a host speaking a newer protocol cannot wedge the stub.
;
; ONE FRAME IN FLIGHT is what keeps the keys whole: the emulated 8042 holds one byte, and a make
; written back to back with its break lost the make (upstream's own injector spaces them 100 ms
; apart). The host's next frame waits for this one's acknowledgement, so between two injections
; the guest has returned from this handler and taken the keyboard's IRQ 1. A button or a position
; goes through the same queue, so a click's press and release keep their order with the keys'.
;
; THE POINTER IS SET (AX=04h) and read back (AX=03h). AX=04h alone moves it without motion, so a
; program that reads the motion counters (AX=0Bh) or a PS/2 mouse of its own would see the pointer
; jump and nothing move; the device's relative motion, signed bytes in the driver's units, goes
; first wherever the build takes it, and AX=04h then lands it exactly. Whether it does is asked
; once at load (`motion`): a build that lacks it flags the device's error bit, and the stub
; still places the pointer. Calling INT 33h from an interrupt handler is sound against DOSBox-X's
; own driver, which is emulator code behind a callback; a mouse driver loaded INSIDE the guest is
; not reached by this route and is not supported. The same holds for the report's INT 10h, which
; DOSBox-X's video BIOS answers behind a callback: under a VBE mode the BIOS mode byte holds the
; emulated card's own number, and only VBE says which mode that is and how large.
;
; It announces itself on the E9 port (`STUB  . scry device=present proto=6 motion=1`) so a host
; reading the log can tell whether the device answered, which protocol it speaks and whether a move
; carries motion, before it trusts the route. A build whose device does not answer exits with a
; code and stays out of memory.
;
; Device protocol (upstream include/iglib.h): index port = base+0, data = base+1, command =
; base+2; a register select is a RESET_LATCH command then four byte writes to the index port
; LSB first; a data write is a RESET_LATCH then four byte writes to the data port LSB first.
; The base port is 0x28.
;
; Build: nasm -f bin scry.asm -o SCRY.COM

        org 100h
        cpu 386

BASE    equ 28h
IDX     equ BASE+0
DAT     equ BASE+1
CMD     equ BASE+2
CMD_RESET_LATCH  equ 00h
CMD_CLEAR_ERROR  equ 0FEh
STATUS_ERROR     equ 02h            ; the status register (CMD read): the last write was refused
REG_IDENTIFY     equ 00000000h
ID_MAGIC         equ 0D05B0740h
REG_KB_INJECT    equ 00804200h      ; sub-selector KB is 0 << 8: the low byte is the scan byte
SUB_MOUSEBTN     equ 0800h          ; sub-selector 8: bit 7 press, low bits the button
SUB_MOTION       equ 0C00h          ; sub-selector 12: X in bits 16-23, Y in 24-31, signed
MOTION_STEP      equ 127            ; the most one signed byte of motion carries
REG_VGA_SIZE     equ 006845C0h      ; height << 16 | width, as the display draws it
REG_SCREENSHOT   equ 00C54010h      ; bit 0: take a screenshot
BIOS_VIDEO_MODE  equ 0449h          ; the BIOS data area's current mode byte (segment 0)
COM1             equ 3F8h
SYNC             equ 0A5h           ; a frame's first byte, host to stub
ACK              equ 5Ah            ; an acknowledgement's first byte, stub to host
STALE_TICKS      equ 3              ; a frame short this many ticks running is dropped

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
        ; copy's queue is left alone. The handlers follow a signature, so a vector itself says
        ; whose it is; its version digit is left out of the comparison, so a copy of another
        ; protocol counts too, and the host reads which one from its announce. Both vectors are
        ; asked: a TSR that hooked INT 1Ch above the first copy hides it there, and IRQ 4's
        ; vector is one nothing else has reason to take.
        cld
        mov     ax, 351Ch
        int     21h                 ; es:bx = the current vector
        mov     cx, tick - signature
        call    resident
        je      .twice
        mov     ax, 350Ch
        int     21h
        mov     cx, serial - signature
        call    resident
        jne     .first
.twice: mov     dx, msg_twice
        call    e9_print
        mov     ax, 4C00h
        int     21h
.first:
        ; --- does the device take relative motion? A build that does not flags an error ---
        mov     al, CMD_CLEAR_ERROR
        mov     dx, CMD
        out     dx, al
        mov     eax, REG_KB_INJECT
        call    write_regsel
        mov     eax, SUB_MOTION    ; no motion at all: a build that takes it moves nothing
        call    write_data
        mov     dx, CMD
        in      al, dx
        test    al, STATUS_ERROR
        setz    byte [motion]
        mov     al, CMD_CLEAR_ERROR
        out     dx, al
        mov     dx, msg_present
        call    e9_print
        mov     al, [motion]
        add     al, '0'
        call    e9_char
        mov     al, 13
        call    e9_char
        mov     al, 10
        call    e9_char
        ; --- the UART: 8N1, divisor 1, an interrupt when a byte arrives ---
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
        xor     al, al              ; no UART interrupts until the handler is in place
        out     dx, al
        ; THE FIFO IS ON: a frame arriving in one burst would otherwise overrun the one-byte
        ; receiver. Its trigger level is one byte, so a frame's first byte raises IRQ 4.
        mov     dx, COM1+2
        mov     al, 07h             ; FCR: enable FIFO, clear both
        out     dx, al
        mov     dx, COM1+4
        mov     al, 0Bh             ; DTR + RTS + OUT2, which gates the UART's IRQ line
        out     dx, al
        ; --- hook IRQ 4 (INT 0Ch), unmask it, then let the UART raise it ---
        mov     ax, 250Ch
        mov     dx, serial
        int     21h
        in      al, 21h
        and     al, 0EFh            ; IRQ 4 unmasked at the master PIC
        out     21h, al
        mov     dx, COM1+1
        mov     al, 01h             ; IER: received data available
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

; ---------------------------------------------------------------- the two entries
; Each runs with interrupts off and `service` never turns them on, so `busy` is only ever found
; set by an entry that came in under a driver call of the stub's own (INT 33h): that entry
; leaves the bytes to the next one.
signature db 'SCRY-INJECT-6'      ; what the already-resident check reads before the entries
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
        cmp     byte [busy], 0
        jne     .out
        mov     byte [ticking], 1
        call    service
.out:   pop     es
        pop     ds
        popad
        iret

serial:                             ; IRQ 4: COM1 received
        pushad
        push    ds
        push    es
        push    cs
        pop     ds
        cld
        cmp     byte [busy], 0
        jne     .eoi
        mov     byte [ticking], 0
        call    service
.eoi:   mov     al, 20h
        out     20h, al
        pop     es
        pop     ds
        popad
        iret

; ---------------------------------------------------------------- the commands
; Bytes are taken off the UART until it is empty, each whole frame carried out and acknowledged
; as it completes; the rest of a short frame waits in `frame` for the next entry. Draining it all
; matters on the interrupt: bytes left behind raise no second IRQ 4.
service:
        mov     byte [busy], 1
        mov     byte [tx_dead], 0   ; this entry's line is given its chance afresh
.more:
        mov     dx, COM1+5
        in      al, dx
        test    al, 1
        jz      .empty
        mov     dx, COM1
        in      al, dx
        cmp     byte [hunting], 0
        je      .take
        cmp     al, SYNC            ; HUNTING: every byte but a SYNC is dropped
        jne     .more
        mov     byte [hunting], 0
        mov     byte [stale], 0
        jmp     .more
.take:  mov     byte [stale], 0
        movzx   bx, byte [got]      ; appended: `parse` has read every byte already there
        mov     [frame+bx], al
        inc     byte [got]
        call    parse
        jmp     .more
.empty:                             ; the UART is drained
        cmp     byte [ticking], 0
        je      .done               ; only a tick counts a short frame's age
        cmp     byte [hunting], 0
        jne     .done
        inc     byte [stale]        ; a frame still short, its SYNC alone included
        cmp     byte [stale], STALE_TICKS
        jb      .done
        mov     byte [hunting], 1   ; dropped: its rest is not coming
        mov     byte [got], 0
        mov     byte [have], 0
.done:  mov     byte [busy], 0
        ret

; Reads `frame` from `have` up to `got`: a frame whole and adding up is carried out; one that
; does not add up, or names no opcode this stub knows, is read again from its first byte.
parse:
.next:  mov     al, [have]
        cmp     al, [got]
        jae     .short
        inc     byte [have]
        cmp     byte [have], 2
        jb      .next               ; the sequence byte alone so far
        ; how long is this frame (sequence byte, opcode, payload, check)?
        mov     al, [frame+1]
        mov     cl, 4
        cmp     al, 'K'
        je      .len
        cmp     al, 'B'
        je      .len
        mov     cl, 7
        cmp     al, 'M'
        je      .len
        mov     cl, 3
        cmp     al, 'R'
        je      .len
        cmp     al, 'S'
        je      .len
        xor     bl, bl              ; an opcode this stub does not know
        jmp     .again
.len:   cmp     [have], cl
        jb      .next
        movzx   cx, cl
        dec     cx                  ; the bytes before the check
        xor     bx, bx
        mov     ah, 0FFh
.sum:   xor     ah, [frame+bx]
        inc     bx
        loop    .sum
        cmp     ah, [frame+bx]
        je      .whole
        xor     bl, bl              ; it does not add up: unacknowledged
        jmp     .again
.whole: inc     bl                  ; past the check: what follows is the next frame's
        push    bx
        call    carry
        pop     bx
.again: call    resync
        jmp     .next
.short: ret

; bl = where in `frame` the next SYNC is looked for. What follows it becomes the frame; with no
; SYNC left, the stub hunts.
resync:
        movzx   bx, bl
.find:  cmp     bl, [got]
        jae     .none
        cmp     byte [frame+bx], SYNC
        je      .found
        inc     bx
        jmp     .find
.none:  mov     byte [hunting], 1
        mov     byte [got], 0
        mov     byte [have], 0
        ret
.found: inc     bx
        xor     di, di
.move:  cmp     bl, [got]
        jae     .moved
        mov     al, [frame+bx]
        mov     [frame+di], al
        inc     bx
        inc     di
        jmp     .move
.moved: mov     ax, di
        mov     [got], al
        mov     byte [have], 0
        mov     byte [stale], 0
        ret

; The frame in `frame` adds up: carried out unless it repeats the last sequence, then acknowledged.
carry:
        mov     al, [frame]
        cmp     al, [last_seq]
        mov     byte [carried], 0
        je      .acked              ; a repeat of the last carried out: acknowledged, not run
        mov     [last_seq], al
        mov     byte [carried], 1
        mov     al, [frame+1]
        cmp     al, 'K'
        jne     .notk
        mov     al, [frame+2]
        call    inject_byte
        jmp     .acked
.notk:  cmp     al, 'B'
        jne     .notb
        movzx   eax, byte [frame+2]
        or      eax, SUB_MOUSEBTN
        call    inject_reg
        jmp     .acked
.notb:  cmp     al, 'M'
        jne     .notm
        cmp     byte [motion], 0
        je      .place
        call    glide
.place: mov     ax, 4
        mov     cx, [frame+2]
        mov     dx, [frame+4]
        int     33h
        jmp     .acked
.notm:  cmp     al, 'R'
        je      .acked              ; the report goes out after its acknowledgement
        mov     eax, REG_SCREENSHOT ; 'S', the last opcode `parse` lets through
        call    write_regsel
        mov     eax, 1
        call    write_data
.acked:
        mov     al, ACK
        call    com_tx
        mov     al, [frame]         ; the sequence byte
        call    com_tx
        mov     al, [frame+1]       ; the opcode
        call    com_tx
        mov     al, [carried]
        call    com_tx
        cmp     byte [frame+1], 'R'
        jne     .out
        mov     byte [to_com], 1    ; the report's text goes to COM1, never to E9
        call    report
        mov     byte [to_com], 0
.out:   ret

; The motion from the driver's pointer to the frame's target, in steps a signed byte holds.
glide:
        mov     ax, 3
        int     33h                 ; cx, dx = where the driver has the pointer
        mov     si, [frame+2]
        sub     si, cx              ; si = x still to go
        mov     di, [frame+4]
        sub     di, dx              ; di = y still to go
.step:  mov     ax, si
        or      ax, di
        jz      .done
        mov     ax, si
        call    clamp
        sub     si, ax
        movzx   ebx, al
        mov     ax, di
        call    clamp
        sub     di, ax
        movzx   eax, al
        shl     eax, 8
        or      eax, ebx
        shl     eax, 16
        or      eax, SUB_MOTION
        call    inject_reg
        jmp     .step
.done:  ret

clamp:                              ; ax, signed, held to one step either way
        cmp     ax, MOTION_STEP
        jle     .low
        mov     ax, MOTION_STEP
.low:   cmp     ax, -MOTION_STEP
        jge     .ok
        mov     ax, -MOTION_STEP
.ok:    ret

; es:bx = a vector, cx = its handler's distance from the signature: ZF set when it is this stub's.
resident:
        cmp     bx, cx
        jb      .no                 ; ZF is clear: bx is not cx
        mov     di, bx
        sub     di, cx
        mov     si, signature
        mov     cx, SIG_LEN - 1
        repe    cmpsb               ; ds:si (ours) against es:di (the vector's owner)
.no:    ret

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
        mov     dx, msg_vbe
        call    e9_print
        mov     ax, 4F03h
        int     10h
        cmp     ax, 004Fh
        je      .vbe
        xor     bx, bx              ; no VBE: mode 0
.vbe:   and     bx, 3FFFh           ; bits 14 and 15 are the frame buffer and the clear, not the mode
        mov     ax, bx
        call    e9_dec
        xor     si, si              ; ModeAttributes, then the resolution: 0 unless VBE says
        xor     cx, cx
        xor     dx, dx
        cmp     bx, 100h
        jb      .tail
        push    cs
        pop     es
        mov     di, vbe_mode_info
        mov     cx, bx
        mov     ax, 4F01h
        int     10h
        xor     cx, cx
        xor     dx, dx
        cmp     ax, 004Fh
        jne     .tail
        mov     si, [vbe_mode_info]
        mov     cx, [vbe_mode_info+12h]
        mov     dx, [vbe_mode_info+14h]
.tail:  push    dx
        push    cx
        mov     dx, msg_attr
        call    e9_print
        mov     ax, si
        call    e9_dec
        mov     dx, msg_res
        call    e9_print
        pop     ax
        call    e9_dec
        mov     al, 'x'
        call    e9_char
        pop     ax
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

e9_char:                            ; al, to E9, or to COM1 while a report is written
        cmp     byte [to_com], 0
        jne     com_tx
        push    dx
        mov     dx, 0E9h
        out     dx, al
        pop     dx
        ret

com_tx:                             ; al -> COM1, once its holding register is empty
        push    dx
        push    cx
        push    ax
        cmp     byte [tx_dead], 0
        jne     .quit               ; the line gave up once in this entry: so does the rest
        mov     dx, COM1+5
        mov     cx, 0FFFFh          ; bounded: a line nobody drains never hangs the handler
.wait:  in      al, dx
        test    al, 20h
        jnz     .ready
        loop    .wait
        mov     byte [tx_dead], 1
.quit:  pop     ax                  ; given up: the byte is dropped
        jmp     .out
.ready: pop     ax
        mov     dx, COM1
        out     dx, al
.out:   pop     cx
        pop     dx
        ret

; ---------------------------------------------------------------- data
old1c       dd 0
; No timestamp: a stamp is the guest program's own clock, and this is not the program.
msg_present db 'STUB  . scry device=present proto=6 motion=$'
msg_rep db 'STUB  . mouse x=$'
msg_y db ' y=$'
msg_b db ' buttons=$'
msg_max db ' max=$'
msg_mode db ' mode=$'
msg_scr db ' screen=$'
msg_vbe db ' vbe=$'
msg_attr db ' attr=$'
msg_res db ' res=$'
hunting db 1         ; between frames: every byte until a SYNC is dropped
got db 0             ; bytes in `frame`, all after the current frame's SYNC
have db 0            ; of those, the bytes `parse` has read
frame times 8 db 0    ; the current frame: sequence byte, opcode, payload, check
to_com db 0          ; 1 while a report is written to COM1
stale db 0           ; ticks the current frame has ended short with nothing arriving
last_seq db 0        ; the sequence byte last carried out; the host never sends 0
motion db 0          ; 1 when the device takes relative motion
carried db 0         ; 1 when this frame was carried out, 0 when it repeated the last
tx_dead db 0         ; 1 once COM1 refused a byte in this entry
busy db 0            ; 1 while `service` runs
ticking db 0         ; 1 when the tick entered `service`, 0 when IRQ 4 did
msg_absent  db 'STUB  . scry device=absent', 13, 10, '$'
msg_twice   db 'STUB  . scry already resident', 13, 10, '$'
vbe_mode_info times 256 db 0    ; INT 10h 4F01h writes the mode's information block here
resident_end:
