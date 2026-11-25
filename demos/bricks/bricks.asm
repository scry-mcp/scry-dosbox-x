; BRICKS: a wall, a ball and a paddle in mode 13h, written to be debugged as much as played.
;
; WHY IT EXISTS. A demo of a debugger needs a program worth stopping: something that moves, keeps
; a score in a variable you can read by name, calls a routine a breakpoint can catch, and answers
; the keyboard and the mouse. And it has to do the same thing every time, or a transcript of one
; run cannot be compared with the next. So there is no random number anywhere: the serve is fixed,
; the ball moves two pixels a frame, and the game is paced by the vertical retrace of a machine
; whose clock the conf pins. Run it twice from cold and the first brick falls on the same frame.
;
; HOW IT PLAYS. Until the first arrow key, or the first mouse motion once M has handed it the
; mouse, it plays itself (the paddle follows the ball), so a machine nobody touches still has a
; game in it. That first input takes control and puts the paddle back in the middle, so what the
; player does next does not depend on where the ball happened to be. Left and right arrows move
; the paddle eight pixels; while M has handed it the mouse (M again takes it back) the paddle
; centres itself under the pointer, read as a POSITION (INT 33h AX=03h) rather than as motion, so a
; caller that puts the pointer at a pixel puts the paddle there, and a pointer moving while the
; game has the keyboard moves nothing. With a player the ball waits on the paddle until SPACE, after the first input
; and after every life lost, so a game nobody is playing at that moment stays exactly where it
; was. ESC returns to DOS. Three lives; a game over goes back to playing itself.
;
; WHAT IT TELLS A DEBUGGER, through the Bochs port 0xE9 (`bochs debug port e9 = true`), one line
; per event: `BRICKS ready`, `HIT <row> <col>`, `KEY L`, `KEY R`, `MOUSE ON`, `MOUSE OFF`,
; `MOUSE`, `PLAYER`, `SERVE`, `LOST`, `GAME OVER`, `CLEAR`.
;
; HOW A CALLER WALKS IT. The one stop of its own is the `int 3` at `ready`, once everything is
; set up: under a session started with `break_on_int3` the guest first stops there, inside the
; program, where its load segment (and so the symbols' base) can be read; outside a debugger
; DOS's own handler returns from it and nothing happens. Load the symbols there, break on
; `brick_hit` (AL = row, BL = column at its entry), and read `score`, `paddle_x` and `ball_x`
; (x, y, dx, dy in its eight bytes) by name.
;
; ITS CONF, `bricks.conf`, boots straight into BRICKS.COM from this directory with the port on.
;
; BUILD, from this directory, with NASM; the symbol table is generated from NASM's own map, so it
; cannot drift from the code (`T` for .text, `D` for the rest, local labels left out):
;
;   nasm -f bin bricks.asm -o BRICKS.COM &&
;   awk '/^---- Section /{t = ($3 == ".text") ? "T" : "D"}
;        NF == 3 && $1 ~ /^[0-9A-F]+$/ && $3 !~ /\./ {
;            a = sprintf("%8s", tolower($2)); gsub(/ /, "0", a); print a, t, $3}' \
;       bricks.map > bricks.sym.tmp && grep -q ' T start$' bricks.sym.tmp &&
;   mv bricks.sym.tmp bricks.sym && rm bricks.map
;
; Chained, and the table checked for `start` before it replaces the old one: a failed assembly
; leaves no map, and an awk over nothing writes an empty table that would load without a word.
;
; The addresses are offsets from the program's segment (`org 0x100`), as `nm` would print them,
; so a debugger places them with `base` = load segment * 16.

        cpu     8086
        org     0x100
        [map symbols bricks.map]

SCREEN_W        equ 320
TOP_Y           equ 12                  ; the ball's ceiling
BRICK_Y         equ 24                  ; the wall's first row
BRICK_ROWS      equ 6
BRICK_COLS      equ 10
BRICK_W         equ 30                  ; one 32-pixel cell less a 2-pixel gap
BRICK_H         equ 8                   ; one 10-pixel row less a 2-pixel gap
BRICKS_ALL      equ BRICK_ROWS * BRICK_COLS
PADDLE_Y        equ 186
PADDLE_W        equ 40
PADDLE_H        equ 4
PADDLE_HOME     equ (SCREEN_W - PADDLE_W) / 2
PADDLE_MIN      equ 2
PADDLE_MAX      equ SCREEN_W - 2 - PADDLE_W
PADDLE_STEP     equ 8                   ; pixels per arrow key
BALL            equ 4                   ; the ball is BALL x BALL pixels
BALL_MIN_X      equ 2
BALL_MAX_X      equ SCREEN_W - 2 - BALL
BALL_LOST_Y     equ 196
SERVE_X         equ 158
SERVE_Y         equ 150
SPEED           equ 2                   ; pixels per frame on each axis
LIVES           equ 3

; Palette entries this program owns, set at start and never taken from the BIOS's defaults.
ROW_PEN         equ 32                  ; 32..37, one per row of the wall
PADDLE_PEN      equ 38
BALL_PEN        equ 15
TEXT_PEN        equ 15

section .text

start:
        mov     ax, 0x0013
        int     0x10
        mov     ax, 0xA000
        mov     es, ax
        call    set_palette
        call    mouse_init
        call    new_game
        mov     si, msg_ready
        call    e9_line
ready:  int     3

main_loop:
        call    retrace
        call    read_input
        call    steer
        call    draw_paddle             ; first, so the paddle's clear never cuts the ball
        call    move_ball
        cmp     byte [quit], 0
        je      main_loop
        mov     ax, 0x0003
        int     0x10
        mov     ax, 0x4C00
        int     0x21

; --- a fresh game: score 0, three lives, the whole wall, the ball served -----------------
new_game:
        mov     word [score], 0
        mov     byte [lives], LIVES
        mov     byte [auto], 1
        mov     word [paddle_x], PADDLE_HOME
        call    fill_wall
        call    draw_screen
        jmp     serve

fill_wall:
        mov     di, bricks
        mov     cx, BRICKS_ALL
        mov     al, 1
.b:     mov     [di], al
        inc     di
        loop    .b
        mov     byte [bricks_left], BRICKS_ALL
        ret

; Playing itself the game serves from a fixed point; with a player the ball waits on the paddle
; until SPACE, so nothing is lost while nobody is pressing anything.
serve:
        call    erase_ball
        cmp     byte [auto], 0
        jne     .fixed
        mov     byte [held], 1
        jmp     carry
.fixed: mov     word [ball_x], SERVE_X
        mov     word [ball_y], SERVE_Y
        mov     word [ball_dx], SPEED
        mov     word [ball_dy], -SPEED
        jmp     draw_ball

; --- the whole screen: cleared, the wall, the status line --------------------------------
draw_screen:
        xor     di, di
        xor     ax, ax
        mov     cx, SCREEN_W * 200 / 2
        rep     stosw
        xor     bx, bx                  ; BL is the row, BH the column
.row:   xor     bh, bh
.col:   call    brick_index
        cmp     byte [bricks + si], 0
        je      .next
        mov     al, ROW_PEN
        add     al, bl
        call    brick_rect
.next:  inc     bh
        cmp     bh, BRICK_COLS
        jb      .col
        inc     bl
        cmp     bl, BRICK_ROWS
        jb      .row
        call    draw_paddle
        jmp     draw_status

; SI = row * BRICK_COLS + column, for BL = row and BH = column.
brick_index:
        mov     al, bl
        mov     ah, BRICK_COLS
        mul     ah
        add     al, bh
        mov     si, ax
        ret

; Fill the brick at BL = row, BH = column with pen AL.
brick_rect:
        push    ax
        mov     al, bl                  ; y = BRICK_Y + row * 10
        mov     ah, 10
        mul     ah
        add     ax, BRICK_Y
        mov     dx, SCREEN_W
        mul     dx
        mov     di, ax
        mov     al, bh                  ; x = column * 32 + 1
        xor     ah, ah
        mov     cl, 5
        shl     ax, cl
        inc     ax
        add     di, ax
        pop     ax
        mov     cx, BRICK_W
        mov     dx, BRICK_H
        jmp     fill_rect

; Fill CX x DX pixels from offset DI with pen AL. Keeps AL.
fill_rect:
        push    di
.line:  push    cx
        push    di
        rep     stosb
        pop     di
        pop     cx
        add     di, SCREEN_W
        dec     dx
        jnz     .line
        pop     di
        ret

; --- the ball -----------------------------------------------------------------------------
move_ball:
        call    erase_ball
        cmp     byte [held], 0
        jne     carry
        mov     ax, [ball_x]            ; the walls
        add     ax, [ball_dx]
        cmp     ax, BALL_MIN_X
        jge     .not_left
        mov     ax, BALL_MIN_X
        neg     word [ball_dx]
.not_left:
        cmp     ax, BALL_MAX_X
        jle     .not_right
        mov     ax, BALL_MAX_X
        neg     word [ball_dx]
.not_right:
        mov     [ball_x], ax
        mov     ax, [ball_y]            ; the ceiling
        add     ax, [ball_dy]
        cmp     ax, TOP_Y
        jge     .not_top
        mov     ax, TOP_Y
        neg     word [ball_dy]
.not_top:
        mov     [ball_y], ax
        call    hit_test
        call    paddle_test
        cmp     word [ball_y], BALL_LOST_Y
        jl      draw_ball
        jmp     lose_life

; Does the ball's centre lie on a standing brick? Then that brick falls.
hit_test:
        mov     ax, [ball_y]
        add     ax, BALL / 2
        sub     ax, BRICK_Y
        jb      .none                   ; above the wall
        mov     cl, 10
        div     cl                      ; AL = row, AH = how far down that row
        cmp     al, BRICK_ROWS
        jae     .none
        cmp     ah, BRICK_H
        jae     .none                   ; in the gap between two rows
        mov     bl, al
        mov     ax, [ball_x]
        add     ax, BALL / 2
        mov     cl, 32
        div     cl                      ; AL = column, AH = how far across that cell
        cmp     ah, 0
        je      .none                   ; in the gap between two columns
        cmp     ah, BRICK_W
        ja      .none
        mov     bh, al
        call    brick_index
        cmp     byte [bricks + si], 0
        je      .none
        mov     al, bl
        mov     bl, bh
        jmp     brick_hit
.none:  ret

; A brick falls: AL = its row, BL = its column. The one place a hit is counted, so a
; breakpoint here sees every brick, with the row and column in registers.
brick_hit:
        mov     bh, bl
        mov     bl, al
        call    brick_index
        mov     byte [bricks + si], 0
        dec     byte [bricks_left]
        push    bx
        xor     al, al
        call    brick_rect
        pop     bx
        mov     al, BRICK_ROWS          ; the top row is worth the most: (6 - row) * 10
        sub     al, bl
        mov     ah, 10
        mul     ah
        add     [score], ax
        neg     word [ball_dy]
        mov     al, bl                  ; HIT <row> <col>
        add     al, '0'
        mov     [msg_hit + 4], al
        mov     al, bh
        add     al, '0'
        mov     [msg_hit + 6], al
        mov     si, msg_hit
        call    e9_line
        call    draw_status
        cmp     byte [bricks_left], 0
        jne     .done
        mov     si, msg_clear
        call    e9_line
        call    fill_wall
        call    draw_screen
        call    serve
.done:  ret

; The ball falling onto the paddle bounces, and which third it lands on steers it.
paddle_test:
        cmp     word [ball_dy], 0
        jle     .none
        mov     ax, [ball_y]
        add     ax, BALL
        cmp     ax, PADDLE_Y
        jl      .none
        cmp     ax, PADDLE_Y + PADDLE_H
        jg      .none
        mov     ax, [ball_x]
        add     ax, BALL / 2
        sub     ax, [paddle_x]
        jb      .none
        cmp     ax, PADDLE_W
        jae     .none
        neg     word [ball_dy]
        mov     word [ball_y], PADDLE_Y - BALL
        cmp     ax, PADDLE_W / 3
        jae     .not_left
        mov     word [ball_dx], -SPEED
.not_left:
        cmp     ax, PADDLE_W - PADDLE_W / 3
        jb      .none
        mov     word [ball_dx], SPEED
.none:  ret

lose_life:
        mov     si, msg_lost
        call    e9_line
        dec     byte [lives]
        jnz     .again
        mov     si, msg_over
        call    e9_line
        jmp     new_game
.again: call    draw_status
        jmp     serve

; The waiting ball sits on the middle of the paddle.
carry:
        mov     ax, [paddle_x]
        add     ax, PADDLE_W / 2 - BALL / 2
        mov     [ball_x], ax
        mov     word [ball_y], PADDLE_Y - BALL
        jmp     draw_ball

erase_ball:
        xor     al, al
        jmp     ball_rect
draw_ball:
        mov     al, BALL_PEN
ball_rect:
        push    ax
        mov     ax, [ball_y]
        mov     dx, SCREEN_W
        mul     dx
        add     ax, [ball_x]
        mov     di, ax
        pop     ax
        mov     cx, BALL
        mov     dx, BALL
        jmp     fill_rect

; --- the paddle ---------------------------------------------------------------------------
; Playing itself, the paddle centres under the ball.
steer:
        cmp     byte [auto], 0
        je      .done
        mov     ax, [ball_x]
        add     ax, BALL / 2 - PADDLE_W / 2
        call    clamp_paddle
        mov     [paddle_x], ax
.done:  ret

; AX clamped to the paddle's range.
clamp_paddle:
        cmp     ax, PADDLE_MIN
        jge     .low_ok
        mov     ax, PADDLE_MIN
.low_ok:
        cmp     ax, PADDLE_MAX
        jle     .high_ok
        mov     ax, PADDLE_MAX
.high_ok:
        ret

; Every frame, whole: the ball's erase can clip the paddle's edge, so redrawing only on a move
; would leave a notch.
draw_paddle:
        mov     di, PADDLE_Y * SCREEN_W + 1   ; the whole row cleared, then the paddle
        mov     cx, SCREEN_W - 2
        mov     dx, PADDLE_H
        xor     al, al
        call    fill_rect
        mov     ax, [paddle_x]
        add     ax, PADDLE_Y * SCREEN_W
        mov     di, ax
        mov     cx, PADDLE_W
        mov     dx, PADDLE_H
        mov     al, PADDLE_PEN
        jmp     fill_rect

; --- input --------------------------------------------------------------------------------
read_input:
        mov     ah, 0x01                ; a key waiting?
        int     0x16
        jz      .mouse
        xor     ah, ah
        int     0x16
        cmp     ah, 0x01                ; ESC
        jne     .not_esc
        mov     byte [quit], 1
        ret
.not_esc:
        cmp     ah, 0x4B
        jne     .not_left
        call    take_control
        mov     ax, [paddle_x]
        sub     ax, PADDLE_STEP
        mov     si, msg_left
        jmp     .moved
.not_left:
        cmp     ah, 0x32                ; M: the mouse takes the paddle, or gives it back
        jne     .not_m
        xor     byte [mouse_on], 1
        mov     si, msg_mouse_on
        jnz     .say
        mov     si, msg_mouse_off
.say:   call    e9_line
        jmp     .mouse
.not_m:
        cmp     ah, 0x39                ; SPACE: the waiting ball goes
        jne     .not_space
        cmp     byte [held], 0
        je      .mouse
        mov     byte [held], 0
        mov     word [ball_dx], SPEED
        mov     word [ball_dy], -SPEED
        mov     si, msg_serve
        call    e9_line
        jmp     .mouse
.not_space:
        cmp     ah, 0x4D
        jne     .mouse
        call    take_control
        mov     ax, [paddle_x]
        add     ax, PADDLE_STEP
        mov     si, msg_right
.moved: call    clamp_paddle
        mov     [paddle_x], ax
        call    e9_line
.mouse: cmp     byte [have_mouse], 0
        je      .done
        mov     ax, 0x0003              ; the pointer's position, read every frame so a move
        int     0x33                    ; made before M is taken as where it starts
        cmp     byte [mouse_on], 0
        je      .seen
        cmp     cx, [pointer_x]
        je      .done
        mov     [pointer_x], cx
        push    cx
        call    take_control
        pop     ax
        shr     ax, 1                   ; mode 13h: the driver counts 640 across 320 pixels
        sub     ax, PADDLE_W / 2
        call    clamp_paddle
        mov     [paddle_x], ax
        mov     si, msg_mouse
        call    e9_line
        ret
.seen:  mov     [pointer_x], cx
.done:  ret

; The first input ends the self-play and starts the player from the middle.
take_control:
        cmp     byte [auto], 0
        je      .done
        mov     byte [auto], 0
        mov     word [paddle_x], PADDLE_HOME
        mov     si, msg_player
        call    e9_line
        call    serve
.done:  ret

mouse_init:
        xor     ax, ax
        int     0x33
        cmp     ax, 0xFFFF              ; a driver answers FFFF, nothing else does
        jne     .none
        mov     byte [have_mouse], 1
        mov     ax, 0x0003              ; where the pointer starts
        int     0x33
        mov     [pointer_x], cx
.none:  ret

; --- the screen's colours -----------------------------------------------------------------
set_palette:
        mov     dx, 0x3C8
        mov     al, ROW_PEN
        out     dx, al
        inc     dx
        mov     si, row_colours
        mov     cx, (row_colours_end - row_colours)
.c:     lodsb
        out     dx, al
        loop    .c
        ret

; --- the status line: SCORE and LIVES through the BIOS, in its own font --------------------
draw_status:
        mov     dx, 0x0001              ; row 0, column 1
        mov     si, msg_score
        call    bios_text
        mov     ax, [score]             ; five digits, from the right
        mov     di, digits + 4
        mov     cx, 5
        mov     bx, 10
.d:     xor     dx, dx
        div     bx
        add     dl, '0'
        mov     [di], dl
        dec     di
        loop    .d
        mov     dx, 0x0007
        mov     si, digits
        call    bios_text
        mov     dx, 0x001B
        mov     si, msg_lives
        call    bios_text
        mov     al, [lives]
        add     al, '0'
        mov     [life_digit], al
        mov     dx, 0x0021
        mov     si, life_digit
        jmp     bios_text

; Write the NUL-terminated SI at row DH, column DL.
bios_text:
        mov     ah, 0x02
        xor     bh, bh
        int     0x10
.ch:    lodsb
        or      al, al
        jz      .done
        mov     ah, 0x0E
        mov     bl, TEXT_PEN
        int     0x10
        jmp     .ch
.done:  ret

; --- the instrumentation line, to the Bochs port ------------------------------------------
e9_line:
        lodsb
        or      al, al
        jz      .end
        out     0xE9, al
        jmp     e9_line
.end:   mov     al, 10
        out     0xE9, al
        ret

; --- one vertical retrace, from its start ---------------------------------------------------
retrace:
        mov     dx, 0x3DA
.out:   in      al, dx
        test    al, 0x08
        jnz     .out
.in:    in      al, dx
        test    al, 0x08
        jz      .in
        ret

section .data

; Six rows from red at the top to blue at the bottom, then the paddle's grey.
row_colours:
        db      0x3F, 0x08, 0x08
        db      0x3F, 0x24, 0x00
        db      0x3F, 0x3C, 0x0C
        db      0x10, 0x3A, 0x10
        db      0x08, 0x34, 0x3A
        db      0x14, 0x18, 0x3F
        db      0x30, 0x30, 0x34
row_colours_end:

msg_ready:      db "BRICKS ready", 0
msg_hit:        db "HIT r c", 0
msg_left:       db "KEY L", 0
msg_right:      db "KEY R", 0
msg_mouse:      db "MOUSE", 0
msg_mouse_on:   db "MOUSE ON", 0
msg_mouse_off:  db "MOUSE OFF", 0
msg_serve:      db "SERVE", 0
msg_player:     db "PLAYER", 0
msg_lost:       db "LOST", 0
msg_over:       db "GAME OVER", 0
msg_clear:      db "CLEAR", 0
msg_score:      db "SCORE", 0
msg_lives:      db "LIVES", 0
digits:         db "00000", 0
life_digit:     db "3", 0

score:          dw 0
lives:          db 0
auto:           db 0
quit:           db 0
have_mouse:     db 0
mouse_on:       db 0
pointer_x:      dw 0                    ; the driver's x at the last frame
held:           db 0
paddle_x:       dw 0
ball_x:         dw 0
ball_y:         dw 0
ball_dx:        dw 0
ball_dy:        dw 0
bricks_left:    db 0
bricks:         times BRICKS_ALL db 0
