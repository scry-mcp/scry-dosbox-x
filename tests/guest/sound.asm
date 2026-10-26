; A guest that sounds, with known answers for the captures: the PC speaker, the OPL2 and the
; MPU-401, all three at once, for as long as it runs.
;
; WHY IT EXISTS. A recording is only as good as the sound it was checked against. A WAV of a
; game proves the file is a WAV; it cannot prove the bytes are the sound, because nobody knows
; what the game played. Here the sound is this file's arithmetic: a 1 kHz square from the PIT
; (1193182 Hz over the divisor 1193), and one OPL2 voice whose registers are the table below.
; A raw OPL capture is held against that table, register for register, and the test reads the
; table out of this file rather than keeping a second copy that could drift.
;
; WHY IT NEVER STOPS SOUNDING. A capture turned on mid-run records only what happens while it
; is on, and both the OPL and the MIDI writers open their file at the first event they see. So
; the loop keys the voice off and on again at every BIOS tick, and sends a MIDI note-on or
; note-off with it: a stretch of a few frames anywhere in the run holds events of both kinds.
;
; ITS CONF RUNS IT AND NOTHING ELSE: `sound.conf` mounts this directory, opens port E9 and runs
; `SOUND.COM`, which never exits. It says `SOUND . tone` on E9 once all three are going.

        cpu     386
        org     0x100

PIT_DIVISOR     equ     1193            ; 1193182 Hz / 1193: a 1 kHz square
OPL_INDEX       equ     0x388
MPU_DATA        equ     0x330
MPU_COMMAND     equ     0x331
KEY_ON          equ     0x20            ; register B0h's key-on bit

start:  mov     si, s_start
        call    emit
        mov     si, opl_table
.reg:   cmp     si, opl_end
        jae     .opl_done
        lodsw                           ; AL = register, AH = value
        call    opl_write
        jmp     .reg
.opl_done:
        mov     si, s_opl
        call    emit
        mov     dx, MPU_COMMAND
        mov     al, 0x3F                ; UART mode: every byte on 330h is MIDI
        out     dx, al
        mov     al, 0xB6                ; PIT channel 2, lobyte/hibyte, square wave
        out     0x43, al
        mov     ax, PIT_DIVISOR
        out     0x42, al
        mov     al, ah
        out     0x42, al
        in      al, 0x61
        or      al, 3                   ; the gate and the speaker on
        out     0x61, al
        mov     si, s_tone
        call    emit

        mov     es, [zero]
        mov     bl, [es:0x46C]          ; the BIOS tick count's low byte
tick:   cmp     bl, [es:0x46C]
        je      tick
        mov     bl, [es:0x46C]
        xor     byte [key], KEY_ON      ; off at one tick, on at the next
        mov     al, 0xB0
        mov     ah, [key_base]
        or      ah, [key]
        call    opl_write
        mov     dx, MPU_DATA
        mov     al, 0x90                ; note-on, channel 1; velocity 0 is a note-off
        out     dx, al
        mov     al, 60                  ; middle C
        out     dx, al
        mov     al, [key]
        add     al, al                  ; 0 or 64
        out     dx, al
        jmp     tick

; --- AL = OPL2 register, AH = value; the waits are the ones the chip's datasheet asks for -----
opl_write:
        push    dx
        push    cx
        mov     dx, OPL_INDEX
        out     dx, al
        mov     cx, 6
.idx:   in      al, dx
        loop    .idx
        inc     dx
        mov     al, ah
        out     dx, al
        dec     dx
        mov     cx, 35
.val:   in      al, dx
        loop    .val
        pop     cx
        pop     dx
        ret

; --- write the NUL-terminated string at SI to port 0xE9 ---------------------------------
emit:   lodsb
        test    al, al
        jz      .done
        out     0xE9, al
        jmp     emit
.done:  ret

; One voice, channel 0, register then value. The last pair keys it on.
opl_table:
        db      0x01, 0x20              ; waveform select enabled
        db      0x20, 0x01              ; modulator: multiple 1
        db      0x40, 0x10              ; modulator: level
        db      0x60, 0xF0              ; modulator: attack, decay
        db      0x80, 0x77              ; modulator: sustain, release
        db      0x23, 0x01              ; carrier: multiple 1
        db      0x43, 0x00              ; carrier: full level
        db      0x63, 0xF0              ; carrier: attack, decay
        db      0x83, 0x77              ; carrier: sustain, release
        db      0xA0, 0x98              ; F-number, low byte
        db      0xB0, 0x31              ; key on, block 4, F-number high bits
opl_end:

key_base:db     0x11                    ; register B0h's value with the key bit clear
key:    db      KEY_ON                  ; the table left the voice keyed on
zero:   dw      0
s_start:db      "SOUND . start", 13, 10, 0
s_opl:  db      "SOUND . opl", 13, 10, 0
s_tone: db      "SOUND . tone", 13, 10, 0
