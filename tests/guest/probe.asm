; A guest this package OWNS, so its live tier needs nobody's project.
;
; WHY IT EXISTS. The tier used to require one private application, and on a machine
; without it NINE cases FAILED rather than skipped -- measured, same emulator and same
; config with one line changed. The dependency was never the project's name: it is that
; the guest RUNS after a `resume` and EMITS instrumentation, which `resume`, `e9`,
; `e9_wait`, `step`-on-a-running-machine and the bound cases all rest on.
;
; WHAT IT EMITS, and every part of it is required by a case rather than decorative:
;
;     [+ 00042.000] PROBE . tick     an ever-rising STAMP. `newest_guest_stamp` reads
;                                    `[+ N.N]` off the log to prove the machine advances
;                                    while nobody asks it anything; without a stamp that
;                                    case cannot tell "never started" from "never moved".
;     [+ 00005.000] PROBE . late     at tick five. The "wait for
;                                    something that has NOT happened yet" case refuses
;                                    to run if its token is already in the log, so a
;                                    steady tick alone makes it INVALID -- measured, it
;                                    found 213 of them and said so.
;
; THE COUNTER IS AN ASCII ODOMETER, incremented digit by digit from the right. A 16-bit
; DIV would cost more code than the whole program and buys nothing: nothing reads this
; as a quantity, only as something that goes up.
;
; IT NEVER EXITS, deliberately: half these cases are about a machine that is still
; running, and a guest that finished would make them measure a dead one.
;
; THE STAMP IS A TICK COUNT AND NOT SECONDS, and nothing reads it as a duration: the
; case that uses it takes the MAXIMUM over the log to prove the machine advanced.
;
; IT WRAPS AT 99999 TICKS, AND THE MAXIMUM IS EXACTLY WHAT A WRAP BREAKS. This comment
; used to say the case "already tolerates" it, citing that case's own docstring about a
; non-monotone log -- which is a different problem with the opposite fix. After a wrap
; the maximum never rises again, so the delta is 0 forever and the case fails
; permanently, blaming a pty deadlock. At ~3 s a line that is about 83 hours into one
; session, so nothing is going to reach it; it is written down because "tolerates" said
; the opposite of the truth and the next person to shorten the delay needs the real
; number, not the reassurance.
;
; MEASURED on this machine at `cycles=fixed 10000`: about one line every three seconds,
; so `late` lands around sixteen seconds in -- well inside the 120 s bound the waiting
; case gives it, and well after the moment that case checks the token is still absent.
;
; The `Bochs port E9h: ` prefix on every line is the EMULATOR's, not this program's.

        cpu     8086
        org     0x100

        ; IT WAITS BEFORE ITS FIRST LINE, and that is not politeness. Two cases prove
        ; the machine is really running by finding DOS's own boot text (`COMMAND.COM`,
        ; `XMS:`, `EMS page frame`) in a screen delta that keeps only its last 2000
        ; characters -- so a guest that starts shouting immediately PUSHES THAT
        ; EVIDENCE OUT and both cases fail for a reason that has nothing to do with
        ; what they test. MEASURED: with no delay they saw only tick lines.
        mov     bx, 300
.settle:mov     cx, 0
.s1:    loop    .s1
        dec     bx
        jnz     .settle

start:  mov     si, tick
        call    emit
        call    bump
        ; THE LATE MILESTONE, when the odometer's last four digits read `0005`.
        ;
        ; THIS COMMENT CARRIED THREE WRONG NUMBERS at once -- "exactly 01000", "tick
        ; 50" and "around five seconds" -- against a test two lines below it that
        ; compares against `00005`, and against this file's own header, which says one
        ; line every three seconds. The `9.6 lines a second` it quoted is the rate
        ; BEFORE the pause below existed, and it survives (correctly) further down as
        ; the measurement that forced the pause.
        ;
        ; SO: tick 5, about sixteen seconds in at the rate the header measures. Late
        ; enough that the waiting case finds the token absent when it asks, early
        ; enough to arrive well inside that case's 120 s bound.
        ;
        ; AND `cnt+0` IS NEVER EXAMINED, so this fires at 00005, 10005, 20005 and so on
        ; -- ten times per wrap, not once. The first is the only one any session
        ; reaches (the second is ~8 hours in) and the waiting case only needs the token
        ; to appear once, so the extra firings cost nothing. Testing the fifth digit
        ; too would be one more `cmp`; it is left out deliberately, and said out loud,
        ; because the file used to claim "ONCE" and that was simply false.
        cmp     word [cnt+1], '00'      ; digits 1 and 2 of "00005"
        jne     .pause
        cmp     word [cnt+3], '05'      ; digits 3 and 4
        jne     .pause
        mov     si, late
        call    emit
        ; A PAUSE LONG ENOUGH THAT THE TERMINAL CAN GO QUIET, which is a stronger
        ; requirement than "does not flood" and is what the measurement forced.
        ; `command()` returns only after `settle` seconds of QUIET, so a guest emitting
        ; continuously means the terminal is NEVER quiet: `resume`'s read then runs to
        ; its timeout and fills with tick lines. MEASURED at ~9.6 lines a second: the
        ; delta came back 3,720 characters of pure ticks, with DOS's own boot banner --
        ; the evidence two cases use to prove the machine really ran -- cut off the
        ; front by the 2000-character cap.
        ;
        ; ~3 SECONDS A LINE, so the terminal settles between them. Several of these
        ; cases want a guest that is busy; none wants one that is talking over them.
.pause: mov     bx, 700
.outer: mov     cx, 0
.spin:  loop    .spin
        dec     bx
        jnz     .outer
        jmp     start

; --- write the NUL-terminated string at SI to port 0xE9 ------------------------
emit:   lodsb
        test    al, al
        jz      .done
        out     0xE9, al
        jmp     emit
.done:  ret

; --- ASCII odometer: bump `cnt`, carrying leftwards ---------------------------
bump:   mov     di, cnt+4
.digit: inc     byte [di]
        cmp     byte [di], '9'
        jbe     .done
        mov     byte [di], '0'
        dec     di
        cmp     di, cnt
        jae     .digit
.done:  ret

tick:   db      "[+ "
cnt:    db      "00000"
        db      ".000] PROBE . tick", 13, 10, 0
late:   db      "[+ 00005.000] PROBE . late", 13, 10, 0
