; MINES: a Minesweeper at VESA 800 x 600 in 256 colours, played with the mouse, written to be
; debugged as much as played.
;
; WHY IT EXISTS. The bricks demo proves the debugger on a mode 13h game driven by keys and one
; mouse position. A program with several screens is a different animal: a title, a board, a menu
; that drops over it and dialogs that sit on top, each of which a caller has to recognise before
; it clicks, on a screen bigger than any BIOS mode. So this one runs in VBE mode 103h and draws
; everything itself through the 64 KB window at A000h, a bank at a time: no linear frame buffer
; and no protected mode, the road a DOS game of the early 90s took, and every byte of its board
; sits in plain memory a debugger can read by name.
;
; HOW IT PLAYS. A click on the title starts a game. Left click reveals a cell, and an empty one
; opens its whole neighbourhood; right click plants or lifts a flag. The menu bar's Game opens a
; menu: New game, Beginner (9 x 9, 10 mines), Intermediate (16 x 16, 40) and Expert (16 x 30,
; 99). Clearing every safe cell wins and a mine loses; either way a dialog says so, and its OK
; starts the next game at the same level. ESC returns to DOS. The pointer is the program's own
; arrow, taken off the screen before anything is drawn and put back after, because DOSBox-X's
; mouse driver draws no pointer in a VBE mode.
;
; NOTHING IS RANDOM. The mines come from a linear congruential generator seeded by the level and
; by how many games have started, so the first beginner board is the same board on every run and
; a transcript of one run can be held against the next. The first click is not protected: a
; player can lose on it, and a debugger that has read the board never does.
;
; IT SOUNDS through a Sound Blaster's digital output: a click for a reveal, a blip for a flag and
; a burst of noise for a mine. Each is an 8-bit sample this program computes at start into a
; buffer that no 64 KB line crosses (the DMA controller's address wraps inside its page), and
; plays as a single-cycle transfer on channel 1 (`BLASTER=A220 I7 D1`, which its conf sets).
; IRQ 7 is masked: nothing waits for a transfer to end, and a new sound simply starts a new one.
;
; WHAT IT TELLS A DEBUGGER, through the Bochs port 0xE9, one line per event: `MINES ready`,
; `TITLE`, `NEW <rows> <cols> <mines>`, `MENU OPEN`, `MENU CLOSE`, `REVEAL <row> <col> <opened>`,
; `FLAG <row> <col>`, `UNFLAG <row> <col>`, `BOOM <row> <col>`, `WIN`, `OK`, `NO SOUND`.
;
; HOW A CALLER WALKS IT. The one stop of its own is the `int 3` at `ready`, once the mode, the
; sounds and the mouse are set up: under a session started with `break_on_int3` the guest first
; stops there, where its load segment (and so the symbols' base) can be read. `rows` and `cols`
; are the board's size in bytes, `mines` its cells row by row (1 a mine), `cells` what the
; player sees (0 hidden, 1 revealed, 2 flagged), and `board_x`, `board_y` the words holding the
; pixel of its top-left corner, each cell CELL pixels square.
;
; ITS CONF, `mines.conf`, boots straight into MINES.COM from this directory with the port on.
;
; BUILD, from this directory, with NASM, the symbol table generated from NASM's own map as the
; bricks demo does (its source says why the chain is written this way):
;
;   nasm -f bin mines.asm -o MINES.COM &&
;   awk '/^---- Section /{t = ($3 == ".text") ? "T" : "D"}
;        NF == 3 && $1 ~ /^[0-9A-F]+$/ && $3 !~ /\./ {
;            a = sprintf("%8s", tolower($2)); gsub(/ /, "0", a); print a, t, $3}' \
;       mines.map > mines.sym.tmp && grep -q ' T start$' mines.sym.tmp &&
;   mv mines.sym.tmp mines.sym && rm mines.map

        cpu     386
        org     0x100
        [map symbols mines.map]

SCREEN_W        equ 800
SCREEN_H        equ 600
VBE_MODE        equ 0x103
CELL            equ 24
MAX_CELLS       equ 16 * 30
BAR_H           equ 24                  ; the menu bar, and the status bar at the bottom
STATUS_Y        equ SCREEN_H - BAR_H
GAME_X          equ 4                   ; the menu bar's Game, as the box a click lands in
GAME_W          equ 48
MENU_W          equ 168
MENU_TOP        equ BAR_H + 2
MENU_ITEM_H     equ 24
MENU_ITEMS      equ 4
DIALOG_X        equ 240
DIALOG_Y        equ 220
DIALOG_W        equ 320
DIALOG_H        equ 140
OK_X            equ 360
OK_Y            equ 316
OK_W            equ 80
OK_H            equ 28
CURSOR_W        equ 8
CURSOR_H        equ 12

; What a click acts on, by the screen it lands on.
ON_TITLE        equ 0
ON_BOARD        equ 1
ON_MENU         equ 2
ON_DIALOG       equ 3

; Palette entries set at start; 0, 14 and 15 are the BIOS's black, yellow and white.
BLACK           equ 0
YELLOW          equ 14
WHITE           equ 15
FACE            equ 32                  ; a hidden cell and the bars
LIGHT           equ 33                  ; a raised edge's lit side
DARK            equ 34                  ; its shaded side, and every rule
OPEN            equ 35                  ; a revealed cell
DESK            equ 36                  ; the background
TITLE_BAR       equ 37
FLAG_RED        equ 38
NUMBER_PEN      equ 39                  ; 40..47 draw the digits 1..8: NUMBER_PEN + n

SB_RESET        equ 0x226
SB_READ         equ 0x22A
SB_WRITE        equ 0x22C
SB_AVAIL        equ 0x22E
SB_RATE_TC      equ 165                 ; 1000000 / (256 - 165): 10989 samples a second
DMA_MASK        equ 0x0A
DMA_MODE        equ 0x0B
DMA_FLIPFLOP    equ 0x0C
DMA1_ADDR       equ 0x02
DMA1_COUNT      equ 0x03
DMA1_PAGE       equ 0x83
DMA1_PLAY       equ 0x49                ; single transfer, memory to card, channel 1
CLICK_LEN       equ 440
BLIP_LEN        equ 880
BOOM_LEN        equ 6600
SOUND_BYTES     equ CLICK_LEN + BLIP_LEN + BOOM_LEN
SOUND_PARAS     equ 0x800               ; 32 KB: whichever side of a 64 KB line in it is longer
                                        ; holds SOUND_BYTES
SND_CLICK       equ 0
SND_BLIP        equ 1
SND_BOOM        equ 2

; A rectangle in pixels, filled with a pen: x, y, w, h, pen.
%macro RECT 5
        mov     byte [pen], %5
        mov     ax, %1
        mov     bx, %2
        mov     cx, %3
        mov     dx, %4
        call    fill_rect
%endmacro

; A rectangle inside the cell `draw_cell` is drawing, from its top-left corner.
%macro CELL_RECT 5
        mov     byte [pen], %5
        mov     ax, [cell_x]
        add     ax, %1
        mov     bx, [cell_y]
        add     bx, %2
        mov     cx, %3
        mov     dx, %4
        call    fill_rect
%endmacro

; A zero-terminated string at x, y, in a pen, at a scale.
%macro TEXT 5
        mov     si, %1
        mov     cx, %2
        mov     dx, %3
        mov     bl, %4
        mov     bh, %5
        call    draw_text
%endmacro

start:
        mov     ah, 0x4A                ; keep 64 KB for this program, give the rest back
        mov     bx, 0x1000
        int     0x21
        call    sounds_init
        mov     ax, 0x4F02
        mov     bx, VBE_MODE
        int     0x10
        cmp     ax, 0x004F
        jne     no_vbe
        call    vbe_init
        call    font_init
        call    palette_init
        call    mouse_init
        mov     si, msg_ready
        call    e9_line
ready:  int     3
        call    show_title
        call    show_pointer

main_loop:
        call    retrace
        mov     ah, 1
        int     0x16
        jz      .mouse
        xor     ah, ah
        int     0x16
        cmp     al, 27
        je      quit
.mouse: call    track_pointer
        mov     ax, 5                   ; left presses since last asked, and where the last was
        xor     bx, bx
        int     0x33
        test    bx, bx
        jz      .right
        call    hide_pointer
        call    on_left
        call    show_pointer
.right: mov     ax, 5
        mov     bx, 1
        int     0x33
        test    bx, bx
        jz      main_loop
        call    hide_pointer
        call    on_right
        call    show_pointer
        jmp     main_loop

quit:   mov     ax, 0x0003
        int     0x10
        mov     ax, 0x4C00
        int     0x21

no_vbe: mov     dx, msg_no_vbe
        mov     ah, 9
        int     0x21
        mov     ax, 0x4C01
        int     0x21

; ---------------------------------------------------------------- the clicks
; cx, dx = the pixel the press was at; the pointer is off the screen while these run.
on_left:
        mov     al, [screen]
        cmp     al, ON_TITLE
        je      new_game
        cmp     al, ON_MENU
        je      menu_click
        cmp     al, ON_DIALOG
        je      dialog_click
        cmp     dx, BAR_H
        jae     .cell
        cmp     cx, GAME_X
        jb      .none
        cmp     cx, GAME_X + GAME_W
        jae     .none
        jmp     open_menu
.cell:  call    cell_at
        jc      .none
        jmp     reveal
.none:  ret

on_right:
        cmp     byte [screen], ON_BOARD
        jne     .none
        call    cell_at
        jc      .none
        jmp     toggle_flag
.none:  ret

; cx, dx = a pixel -> al = row, ah = column, bx = the cell's index; carry when off the board.
cell_at:
        sub     cx, [board_x]
        jb      .off
        sub     dx, [board_y]
        jb      .off
        mov     bx, CELL
        push    dx
        mov     ax, cx
        xor     dx, dx
        div     bx                      ; ax = column
        pop     dx
        cmp     al, [cols]
        jae     .off
        mov     cl, al
        mov     ax, dx
        xor     dx, dx
        div     bx                      ; ax = row
        cmp     al, [rows]
        jae     .off
        mov     ah, cl
        call    index_of
        clc
        ret
.off:   stc
        ret

; al = row, ah = column -> bx = row * cols + column; every other register kept.
index_of:
        push    ax
        push    dx
        mov     bl, ah
        xor     bh, bh
        mov     dl, [cols]
        mul     dl
        add     bx, ax
        pop     dx
        pop     ax
        ret

; bx = an index -> al = row, ah = column.
row_col_of:
        push    dx
        mov     ax, bx
        mov     dl, [cols]
        div     dl
        pop     dx
        ret

; ---------------------------------------------------------------- the game
new_game:
        movzx   ebx, byte [level]
        mov     al, [level_rows + ebx]
        mov     [rows], al
        mov     ah, [level_cols + ebx]
        mov     [cols], ah
        mul     ah
        mov     [total], ax
        mov     ax, [level_mines + ebx * 2]
        mov     [mine_count], ax
        mov     cx, [total]
        sub     cx, ax
        mov     [cells_left], cx
        mov     word [flags], 0
        mov     byte [lost], 0
        mov     word [boom_at], 0xFFFF
        movzx   ax, byte [cols]         ; centred between the two bars
        imul    ax, ax, CELL
        neg     ax
        add     ax, SCREEN_W
        shr     ax, 1
        mov     [board_x], ax
        movzx   ax, byte [rows]
        imul    ax, ax, CELL
        neg     ax
        add     ax, STATUS_Y - BAR_H
        shr     ax, 1
        add     ax, BAR_H
        mov     [board_y], ax
        mov     di, mines
        mov     cx, MAX_CELLS * 2       ; `mines` and `cells` lie side by side
        xor     al, al
        push    ds
        pop     es
        rep     stosb
        movzx   eax, byte [level]       ; the seed: the level and the games started so far
        shl     eax, 16
        mov     ax, [games]
        add     eax, 0x5EED
        mov     [seed], eax
        inc     word [games]
        mov     cx, [mine_count]
.place: call    rand
        xor     edx, edx
        movzx   ebx, word [total]
        div     ebx
        cmp     byte [mines + edx], 0
        jne     .place                  ; taken: draw again, the count unspent
        mov     byte [mines + edx], 1
        loop    .place
        mov     byte [screen], ON_BOARD
        mov     si, msg_new
        call    e9_str
        movzx   ax, byte [rows]
        call    e9_dec
        call    e9_space
        movzx   ax, byte [cols]
        call    e9_dec
        call    e9_space
        mov     ax, [mine_count]
        call    e9_dec
        call    e9_newline
        jmp     draw_board_screen

; eax = the next number of the sequence, 0..7FFFh.
rand:
        mov     eax, [seed]
        imul    eax, eax, 1103515245
        add     eax, 12345
        mov     [seed], eax
        shr     eax, 16
        and     eax, 0x7FFF
        ret

; al = row, ah = column, bx = the cell: a hidden one is revealed, and an empty one opens its
; neighbours, a cell at a time off `queue`, each marked revealed as it is queued so none is
; queued twice.
reveal:
        cmp     byte [cells + bx], 0
        jne     .none
        cmp     byte [mines + bx], 0
        jne     explode
        mov     [at_row], al
        mov     [at_col], ah
        mov     word [opened], 0
        mov     byte [cells + bx], 1
        mov     [queue], bx
        mov     word [queue_top], queue + 2
.next:  mov     di, [queue_top]
        cmp     di, queue
        je      .done
        sub     di, 2
        mov     [queue_top], di
        mov     bx, [di]
        inc     word [opened]
        dec     word [cells_left]
        call    row_col_of
        call    draw_cell
        call    count_adjacent
        test    cl, cl
        jnz     .next
        mov     si, queue_hidden
        call    each_neighbour
        jmp     .next
.done:  mov     si, msg_reveal
        call    e9_str
        call    e9_at
        call    e9_space
        mov     ax, [opened]
        call    e9_dec
        call    e9_newline
        mov     si, SND_CLICK
        call    play_sound
        cmp     word [cells_left], 0
        je      win
.none:  ret

queue_hidden:                           ; `each_neighbour`'s visit: a hidden cell joins the queue
        cmp     byte [cells + bx], 0
        jne     .out
        mov     byte [cells + bx], 1
        mov     di, [queue_top]
        mov     [di], bx
        add     word [queue_top], 2
.out:   ret

; al = row, ah = column -> cl = the mines around it.
count_adjacent:
        push    si
        mov     byte [adjacent], 0
        mov     si, .mine
        call    each_neighbour
        mov     cl, [adjacent]
        pop     si
        ret
.mine:  cmp     byte [mines + bx], 0
        je      .out
        inc     byte [adjacent]
.out:   ret

; al = row, ah = column; si = a routine called with al, ah and bx set to each neighbour on the
; board. Every register comes back as it went in.
each_neighbour:
        pushad
        mov     [around_row], al
        mov     [around_col], ah
        mov     dh, -1
.row:   mov     dl, -1
.col:   mov     al, [around_row]
        add     al, dh
        mov     ah, [around_col]
        add     ah, dl
        mov     cx, dx
        or      cl, ch
        jz      .next                   ; the cell itself
        cmp     al, [rows]              ; one above the top row is 255, past every size
        jae     .next
        cmp     ah, [cols]
        jae     .next
        call    index_of
        push    dx
        push    si
        call    si
        pop     si
        pop     dx
.next:  inc     dl
        cmp     dl, 2
        jne     .col
        inc     dh
        cmp     dh, 2
        jne     .row
        popad
        ret

explode:
        mov     [at_row], al
        mov     [at_col], ah
        mov     [boom_at], bx
        mov     byte [lost], 1
        mov     si, msg_boom
        call    e9_str
        call    e9_at
        call    e9_newline
        mov     si, SND_BOOM
        call    play_sound
        xor     bx, bx
.mine:  cmp     byte [mines + bx], 0
        je      .next
        mov     byte [cells + bx], 1
        call    row_col_of
        call    draw_cell
.next:  inc     bx
        cmp     bx, [total]
        jb      .mine
        mov     si, msg_lose_title
        mov     di, msg_lose_body
        jmp     open_dialog

win:
        xor     bx, bx
.mine:  cmp     byte [mines + bx], 0
        je      .next
        mov     byte [cells + bx], 2
        call    row_col_of
        call    draw_cell
.next:  inc     bx
        cmp     bx, [total]
        jb      .mine
        mov     ax, [mine_count]
        mov     [flags], ax
        call    draw_status
        mov     si, msg_win
        call    e9_line
        mov     si, msg_win_title
        mov     di, msg_win_body
        jmp     open_dialog

; al = row, ah = column, bx = the cell: a hidden cell takes a flag, a flagged one loses it.
toggle_flag:
        mov     cl, [cells + bx]
        cmp     cl, 1
        je      .none
        mov     [at_row], al
        mov     [at_col], ah
        xor     cl, 2
        mov     [cells + bx], cl
        mov     si, msg_flag
        inc     word [flags]
        test    cl, cl
        jnz     .said
        mov     si, msg_unflag
        sub     word [flags], 2
.said:  call    e9_str
        call    e9_at
        call    e9_newline
        mov     al, [at_row]
        mov     ah, [at_col]
        call    draw_cell
        call    draw_status
        mov     si, SND_BLIP
        call    play_sound
.none:  ret

open_menu:
        mov     byte [screen], ON_MENU
        mov     si, msg_menu_open
        call    e9_line
        jmp     draw_menu

; cx, dx = the click: an item acts, anywhere else closes the menu.
menu_click:
        mov     byte [screen], ON_BOARD
        mov     si, msg_menu_close
        call    e9_line
        cmp     cx, MENU_W
        jae     .closed
        sub     dx, MENU_TOP
        jb      .closed
        mov     ax, dx
        xor     dx, dx
        mov     bx, MENU_ITEM_H
        div     bx
        cmp     ax, MENU_ITEMS
        jae     .closed
        test    ax, ax
        jz      .new                    ; New game keeps the level
        dec     al
        mov     [level], al
.new:   jmp     new_game
.closed:
        jmp     draw_board_screen

dialog_click:
        cmp     cx, OK_X
        jb      .none
        cmp     cx, OK_X + OK_W
        jae     .none
        cmp     dx, OK_Y
        jb      .none
        cmp     dx, OK_Y + OK_H
        jae     .none
        mov     si, msg_ok
        call    e9_line
        jmp     new_game
.none:  ret

; si = the dialog's title, di = its line.
open_dialog:
        mov     byte [screen], ON_DIALOG
        push    di
        push    si
        RECT    DIALOG_X, DIALOG_Y, DIALOG_W, DIALOG_H, DARK
        RECT    DIALOG_X + 2, DIALOG_Y + 2, DIALOG_W - 4, DIALOG_H - 4, FACE
        RECT    DIALOG_X + 2, DIALOG_Y + 2, DIALOG_W - 4, 24, TITLE_BAR
        pop     si
        mov     cx, DIALOG_X + 12
        mov     dx, DIALOG_Y + 6
        mov     bx, (1 << 8) | WHITE
        call    draw_text
        pop     si
        mov     cx, DIALOG_X + 20
        mov     dx, DIALOG_Y + 48
        mov     bx, (1 << 8) | BLACK
        call    draw_text
        mov     ax, OK_X
        mov     bx, OK_Y
        mov     cx, OK_W
        mov     dx, OK_H
        call    raised
        TEXT    msg_ok_button, OK_X + 32, OK_Y + 6, BLACK, 1
        ret

; ---------------------------------------------------------------- the screens
show_title:
        mov     byte [screen], ON_TITLE
        RECT    0, 0, SCREEN_W, SCREEN_H, DESK
        TEXT    msg_title, 228, 184, BLACK, 4
        TEXT    msg_title, 224, 180, WHITE, 4
        TEXT    msg_start, 216, 300, YELLOW, 2
        TEXT    msg_how, 164, 360, WHITE, 1
        TEXT    msg_esc, 328, 384, WHITE, 1
        mov     si, msg_title_line
        jmp     e9_line

draw_board_screen:
        RECT    0, 0, SCREEN_W, SCREEN_H, DESK
        RECT    0, 0, SCREEN_W, BAR_H, FACE
        RECT    0, BAR_H - 1, SCREEN_W, 1, DARK
        TEXT    msg_game, GAME_X + 8, 4, BLACK, 1
        call    draw_status
        movzx   cx, byte [cols]         ; a sunken rule round the board
        imul    cx, cx, CELL
        add     cx, 6
        movzx   dx, byte [rows]
        imul    dx, dx, CELL
        add     dx, 6
        mov     ax, [board_x]
        sub     ax, 3
        mov     bx, [board_y]
        sub     bx, 3
        mov     byte [pen], DARK
        call    fill_rect
        xor     bx, bx
.cell:  call    row_col_of
        call    draw_cell
        inc     bx
        cmp     bx, [total]
        jb      .cell
        ret

draw_status:
        RECT    0, STATUS_Y, SCREEN_W, BAR_H, FACE
        RECT    0, STATUS_Y, SCREEN_W, 1, DARK
        TEXT    msg_left, 12, STATUS_Y + 4, BLACK, 1
        mov     ax, [mine_count]        ; the flags still to plant, never below zero
        sub     ax, [flags]
        jns     .count
        xor     ax, ax
.count: mov     di, number_text
        call    three_digits
        TEXT    number_text, 12 + 12 * 8, STATUS_Y + 4, BLACK, 1
        movzx   ebx, byte [level]
        mov     si, [level_names + ebx * 2]
        mov     cx, 640
        mov     dx, STATUS_Y + 4
        mov     bx, (1 << 8) | BLACK
        jmp     draw_text

draw_menu:
        RECT    0, BAR_H, MENU_W, MENU_ITEMS * MENU_ITEM_H + 4, DARK
        RECT    1, BAR_H + 1, MENU_W - 2, MENU_ITEMS * MENU_ITEM_H + 2, FACE
        TEXT    msg_item_new, 12, MENU_TOP + 4, BLACK, 1
        TEXT    msg_beginner, 12, MENU_TOP + 4 + MENU_ITEM_H, BLACK, 1
        TEXT    msg_intermediate, 12, MENU_TOP + 4 + 2 * MENU_ITEM_H, BLACK, 1
        TEXT    msg_expert, 12, MENU_TOP + 4 + 3 * MENU_ITEM_H, BLACK, 1
        movzx   dx, byte [level]        ; the level in play, marked beside its item
        inc     dx
        imul    dx, dx, MENU_ITEM_H
        add     dx, MENU_TOP + 4
        TEXT    msg_mark, MENU_W - 20, dx, BLACK, 1
        ret

; al = row, ah = column: the cell as the player sees it.
draw_cell:
        pushad
        call    index_of
        mov     [cell_index], bx
        movzx   cx, ah
        imul    cx, cx, CELL
        add     cx, [board_x]
        mov     [cell_x], cx
        movzx   dx, al
        imul    dx, dx, CELL
        add     dx, [board_y]
        mov     [cell_y], dx
        mov     dl, [cells + bx]
        cmp     dl, 1
        je      .open
        push    dx
        mov     ax, [cell_x]
        mov     bx, [cell_y]
        mov     cx, CELL
        mov     dx, CELL
        call    raised
        pop     dx
        cmp     dl, 2
        jne     .done
        CELL_RECT 11, 5, 2, 14, BLACK
        CELL_RECT 5, 5, 7, 7, FLAG_RED
        CELL_RECT 6, 18, 12, 2, BLACK
        jmp     .done
.open:  mov     byte [pen], OPEN
        mov     bx, [cell_index]
        cmp     bx, [boom_at]
        jne     .face
        mov     byte [pen], FLAG_RED
.face:  mov     ax, [cell_x]
        mov     bx, [cell_y]
        mov     cx, CELL
        mov     dx, CELL
        call    fill_rect
        CELL_RECT 0, 0, CELL, 1, DARK
        CELL_RECT 0, 0, 1, CELL, DARK
        mov     bx, [cell_index]
        cmp     byte [mines + bx], 0
        je      .number
        CELL_RECT 7, 9, 10, 6, BLACK
        CELL_RECT 9, 7, 6, 10, BLACK
        CELL_RECT 9, 9, 2, 2, WHITE
        jmp     .done
.number:
        call    row_col_of
        call    count_adjacent
        test    cl, cl
        jz      .done
        mov     al, cl
        add     al, '0'
        mov     bl, cl
        add     bl, NUMBER_PEN
        mov     bh, 1
        mov     cx, [cell_x]
        add     cx, 8
        mov     dx, [cell_y]
        add     dx, 4
        call    draw_char
.done:  popad
        ret

; ax, bx = a box's corner, cx, dx = its size: a face with a lit top-left and a shaded
; bottom-right, two pixels each.
raised:
        pushad
        mov     [box + 0], ax
        mov     [box + 2], bx
        mov     [box + 4], cx
        mov     [box + 6], dx
        mov     byte [pen], FACE
        call    fill_rect
        mov     byte [pen], LIGHT
        mov     dx, 2
        call    fill_rect               ; the top
        mov     cx, 2
        mov     dx, [box + 6]
        call    fill_rect               ; the left
        mov     byte [pen], DARK
        add     ax, [box + 4]
        sub     ax, 2
        call    fill_rect               ; the right
        mov     ax, [box + 0]
        mov     bx, [box + 2]
        add     bx, [box + 6]
        sub     bx, 2
        mov     cx, [box + 4]
        mov     dx, 2
        call    fill_rect               ; the bottom
        popad
        ret

; ---------------------------------------------------------------- pixels
; ax = x, bx = y, cx = width, dx = height, [pen] = the colour; every register kept. A row is
; written a span at a time, split where it crosses into the next 64 KB bank.
fill_rect:
        pushad
        push    es
        mov     es, [win_seg]
        movzx   eax, ax
        movzx   ebx, bx
        movzx   ecx, cx
        movzx   edx, dx
        test    ecx, ecx
        jz      .out
        test    edx, edx
        jz      .out
        imul    ebx, ebx, SCREEN_W
        add     ebx, eax                ; the first row's first pixel, linear
        mov     [fill_w], ecx
.row:   mov     esi, [fill_w]
        mov     eax, ebx
.span:  call    set_bank                ; di = where eax falls in the window
        mov     ecx, 0x10000
        movzx   edi, di
        sub     ecx, edi
        cmp     ecx, esi
        jbe     .fits
        mov     ecx, esi
.fits:  sub     esi, ecx
        add     eax, ecx
        push    eax
        mov     al, [pen]
        rep     stosb
        pop     eax
        test    esi, esi
        jnz     .span
        add     ebx, SCREEN_W
        dec     edx
        jnz     .row
.out:   pop     es
        popad
        ret

; eax = a linear pixel -> di = its offset in the window, the window moved to its bank.
set_bank:
        push    eax
        push    ebx
        push    edx
        mov     di, ax
        shr     eax, 16
        cmp     ax, [bank]
        je      .same
        mov     [bank], ax
        mul     word [bank_step]
        mov     dx, ax
        mov     ax, 0x4F05
        xor     bx, bx
        int     0x10
.same:  pop     edx
        pop     ebx
        pop     eax
        ret

; ax = x, bx = y -> es:di = the pixel, its bank set; es is the window's.
pixel_at:
        push    eax
        push    ebx
        movzx   eax, ax
        movzx   ebx, bx
        imul    ebx, ebx, SCREEN_W
        add     eax, ebx
        call    set_bank
        mov     es, [win_seg]
        pop     ebx
        pop     eax
        ret

; ---------------------------------------------------------------- text
; si = a zero-terminated string, cx = x, dx = y, bl = pen, bh = scale.
draw_text:
        pushad
.next:  lodsb
        test    al, al
        jz      .out
        call    draw_char
        movzx   ax, bh
        shl     ax, 3
        add     cx, ax
        jmp     .next
.out:   popad
        ret

; al = a character of the BIOS's 8 x 16 font, cx = x, dx = y, bl = pen, bh = scale.
draw_char:
        pushad
        push    es
        mov     [pen], bl
        mov     [glyph_x], cx
        mov     [glyph_y], dx
        movzx   bp, bh
        movzx   si, al
        shl     si, 4
        add     si, [font_off]
        mov     es, [font_seg]
        xor     di, di                  ; the glyph's row
.row:   mov     al, [es:si]
        inc     si
        mov     [glyph_bits], al
        xor     bx, bx                  ; its column
.col:   shl     byte [glyph_bits], 1
        jnc     .skip
        push    bx
        mov     ax, bx
        mul     bp
        add     ax, [glyph_x]
        push    ax
        mov     ax, di
        mul     bp
        add     ax, [glyph_y]
        mov     bx, ax
        pop     ax
        mov     cx, bp
        mov     dx, bp
        call    fill_rect
        pop     bx
.skip:  inc     bx
        cmp     bx, 8
        jb      .col
        inc     di
        cmp     di, 16
        jb      .row
        pop     es
        popad
        ret

; ax = a number below 1000 -> three digits at di, zero-terminated.
three_digits:
        pushad
        mov     bx, 10
        mov     cx, 3
        add     di, 3
        mov     byte [di], 0
.digit: dec     di
        xor     dx, dx
        div     bx
        add     dl, '0'
        mov     [di], dl
        loop    .digit
        popad
        ret

; ---------------------------------------------------------------- the pointer
track_pointer:
        mov     ax, 3
        int     0x33
        cmp     cx, [pointer_x]
        jne     .moved
        cmp     dx, [pointer_y]
        je      .still
.moved: push    dx
        push    cx
        call    hide_pointer
        pop     word [pointer_x]
        pop     word [pointer_y]
        call    show_pointer
.still: ret

; The arrow drawn at the pointer, what it covers kept in `under` to put back.
show_pointer:
        cmp     byte [pointer_on], 0
        jne     .out
        mov     byte [pointer_on], 1
        mov     si, under
        call    each_arrow_pixel
.out:   ret

hide_pointer:
        cmp     byte [pointer_on], 0
        je      .out
        mov     byte [pointer_on], 0
        mov     si, 0
        call    each_arrow_pixel
.out:   ret

; si = `under`: save each pixel the arrow covers and draw the arrow; si = 0: put them back.
each_arrow_pixel:
        pushad
        push    es
        xor     bp, bp                  ; the arrow's row
.row:   mov     dl, [arrow_black + bp]
        mov     dh, [arrow_white + bp]
        xor     cx, cx                  ; its column
.col:   mov     al, dl
        or      al, dh
        shl     al, cl
        test    al, 0x80
        jz      .next
        mov     ax, [pointer_x]
        add     ax, cx
        cmp     ax, SCREEN_W
        jae     .next
        mov     bx, [pointer_y]
        add     bx, bp
        cmp     bx, SCREEN_H
        jae     .next
        call    pixel_at
        mov     bx, bp
        shl     bx, 3
        add     bx, cx                  ; the pixel's slot in `under`
        test    si, si
        jz      .back
        mov     al, [es:di]
        mov     [under + bx], al
        mov     al, BLACK
        mov     ah, dh
        shl     ah, cl
        test    ah, 0x80
        jz      .ink
        mov     al, WHITE
.ink:   mov     [es:di], al
        jmp     .next
.back:  mov     al, [under + bx]
        mov     [es:di], al
.next:  inc     cx
        cmp     cx, CURSOR_W
        jb      .col
        inc     bp
        cmp     bp, CURSOR_H
        jb      .row
        pop     es
        popad
        ret

; ---------------------------------------------------------------- set up
vbe_init:
        push    ds
        pop     es
        mov     ax, 0x4F01
        mov     cx, VBE_MODE
        mov     di, mode_info
        int     0x10
        mov     ax, 64                  ; the window moves in steps of its granularity, in KB
        xor     dx, dx
        div     word [mode_info + 4]
        mov     [bank_step], ax
        mov     ax, [mode_info + 8]
        mov     [win_seg], ax
        ret

font_init:
        push    es
        push    bp
        mov     ax, 0x1130
        mov     bh, 6                   ; the 8 x 16 font
        int     0x10
        mov     [font_off], bp
        mov     [font_seg], es
        pop     bp
        pop     es
        ret

palette_init:
        mov     si, palette
.next:  lodsb
        test    al, al
        jz      .out
        movzx   bx, al
        lodsb
        mov     dh, al
        lodsb
        mov     ch, al
        lodsb
        mov     cl, al
        mov     ax, 0x1010
        int     0x10
        jmp     .next
.out:   ret

mouse_init:
        xor     ax, ax
        int     0x33
        mov     ax, 7
        xor     cx, cx
        mov     dx, SCREEN_W - 1
        int     0x33
        mov     ax, 8
        xor     cx, cx
        mov     dx, SCREEN_H - 1
        int     0x33
        mov     ax, 4
        mov     cx, SCREEN_W / 2
        mov     dx, SCREEN_H / 2
        int     0x33
        mov     word [pointer_x], SCREEN_W / 2
        mov     word [pointer_y], SCREEN_H / 2
        ret

; ---------------------------------------------------------------- sound
; A buffer from DOS, the sounds placed on whichever side of a 64 KB line in it is long enough,
; computed, and the card reset; without a card the game is silent and says so.
sounds_init:
        mov     ah, 0x48
        mov     bx, SOUND_PARAS
        int     0x21
        jc      .silent
        movzx   eax, ax
        shl     eax, 4
        mov     ebx, eax
        add     ebx, 0xFFFF
        and     ebx, 0xFFFF0000         ; the first 64 KB line at or past the buffer
        mov     ecx, ebx
        sub     ecx, eax
        cmp     ecx, SOUND_BYTES
        jae     .placed
        mov     eax, ebx
.placed:
        mov     [sound_phys], eax
        shr     eax, 4
        mov     [sound_seg], ax
        call    make_sounds
        call    sb_reset
        ret
.silent:
        mov     si, msg_silent
        jmp     e9_line

make_sounds:
        push    es
        mov     es, [sound_seg]
        xor     di, di
        xor     cx, cx                  ; the click: a 1.2 kHz square fading out
.click: mov     ax, CLICK_LEN
        sub     ax, cx
        shl     ax, 6
        xor     dx, dx
        mov     bx, CLICK_LEN
        div     bx
        mov     bl, al                  ; the amplitude, 64 down to 0
        mov     ax, cx
        xor     dx, dx
        mov     si, 9
        div     si
        mov     al, 128
        cmp     dx, 4
        jb      .up
        sub     al, bl
        jmp     .click_out
.up:    add     al, bl
.click_out:
        stosb
        inc     cx
        cmp     cx, CLICK_LEN
        jb      .click
        xor     cx, cx                  ; the blip: 785 Hz, then an octave up
.blip:  mov     si, 14
        cmp     cx, BLIP_LEN / 2
        jb      .low
        mov     si, 7
.low:   mov     ax, cx
        xor     dx, dx
        div     si
        shr     si, 1
        mov     al, 128 + 48
        cmp     dx, si
        jb      .blip_out
        mov     al, 128 - 48
.blip_out:
        stosb
        inc     cx
        cmp     cx, BLIP_LEN
        jb      .blip
        xor     cx, cx                  ; the mine: noise fading out, smoothed by a neighbour
        mov     bx, 0xACE1              ; the noise register
        mov     byte [last_sample], 128
.boom:  shr     bx, 1
        jnc     .bit
        xor     bx, 0xB400
.bit:   mov     ax, BOOM_LEN
        sub     ax, cx
        xor     dx, dx
        mov     si, BOOM_LEN / 100
        div     si                      ; ax = the amplitude, 100 down to 0
        mov     si, ax
        mov     al, bl
        sub     al, 128
        cbw
        imul    si
        sar     ax, 7
        add     ax, 128
        movzx   dx, byte [last_sample]
        add     ax, dx
        shr     ax, 1
        mov     [last_sample], al
        stosb
        inc     cx
        cmp     cx, BOOM_LEN
        jb      .boom
        pop     es
        ret

sb_reset:
        mov     dx, SB_RESET
        mov     al, 1
        out     dx, al
        in      al, dx                  ; the reset line held a few microseconds
        in      al, dx
        in      al, dx
        in      al, dx
        xor     al, al
        out     dx, al
        mov     cx, 0xFFFF
.wait:  mov     dx, SB_AVAIL
        in      al, dx
        test    al, 0x80
        jnz     .read
        loop    .wait
        jmp     .none
.read:  mov     dx, SB_READ
        in      al, dx
        cmp     al, 0xAA
        jne     .none
        mov     byte [sound_on], 1
        mov     al, 0xD1                ; the speaker on
        call    dsp_write
        in      al, 0x21
        or      al, 0x80                ; IRQ 7 masked: no transfer's end is waited for
        out     0x21, al
        ret
.none:  mov     si, msg_silent
        jmp     e9_line

dsp_write:
        push    dx
        push    ax
        mov     dx, SB_WRITE
.busy:  in      al, dx
        test    al, 0x80
        jnz     .busy
        pop     ax
        out     dx, al
        pop     dx
        ret

; si = SND_CLICK, SND_BLIP or SND_BOOM.
play_sound:
        cmp     byte [sound_on], 0
        je      .out
        pushad
        mov     dx, SB_AVAIL            ; the last transfer's interrupt acknowledged
        in      al, dx
        mov     ebx, esi
        and     ebx, 0xFFFF
        movzx   ecx, word [sound_len + ebx * 2]
        dec     cx
        movzx   ebx, word [sound_start + ebx * 2]
        add     ebx, [sound_phys]
        mov     al, 4 | 1
        out     DMA_MASK, al
        xor     al, al
        out     DMA_FLIPFLOP, al
        mov     al, DMA1_PLAY
        out     DMA_MODE, al
        mov     al, bl
        out     DMA1_ADDR, al
        mov     al, bh
        out     DMA1_ADDR, al
        shr     ebx, 16
        mov     al, bl
        out     DMA1_PAGE, al
        mov     al, cl
        out     DMA1_COUNT, al
        mov     al, ch
        out     DMA1_COUNT, al
        mov     al, 1
        out     DMA_MASK, al
        mov     al, 0x40
        call    dsp_write
        mov     al, SB_RATE_TC
        call    dsp_write
        mov     al, 0x14                ; 8-bit, single cycle, its length less one
        call    dsp_write
        mov     al, cl
        call    dsp_write
        mov     al, ch
        call    dsp_write
        popad
.out:   ret

; ---------------------------------------------------------------- the E9 port
e9_line:
        call    e9_str
        jmp     e9_newline

e9_str:                                 ; si = a zero-terminated string
        push    ax
        push    si
.next:  lodsb
        test    al, al
        jz      .out
        out     0xE9, al
        jmp     .next
.out:   pop     si
        pop     ax
        ret

e9_at:                                  ; `<row> <col>` of the last cell acted on
        movzx   ax, byte [at_row]
        call    e9_dec
        call    e9_space
        movzx   ax, byte [at_col]
        jmp     e9_dec

e9_dec:                                 ; ax, unsigned
        pushad
        xor     cx, cx
        mov     bx, 10
.split: xor     dx, dx
        div     bx
        push    dx
        inc     cx
        test    ax, ax
        jnz     .split
.emit:  pop     ax
        add     al, '0'
        out     0xE9, al
        loop    .emit
        popad
        ret

e9_space:
        push    ax
        mov     al, ' '
        out     0xE9, al
        pop     ax
        ret

e9_newline:
        push    ax
        mov     al, 13
        out     0xE9, al
        mov     al, 10
        out     0xE9, al
        pop     ax
        ret

retrace:
        mov     dx, 0x3DA
.out:   in      al, dx
        test    al, 8
        jnz     .out
.in:    in      al, dx
        test    al, 8
        jz      .in
        ret

; ---------------------------------------------------------------- data
section .data
level_rows      db 9, 16, 16
level_cols      db 9, 16, 30
level_mines     dw 10, 40, 99
level_names     dw msg_beginner, msg_intermediate, msg_expert
sound_start     dw 0, CLICK_LEN, CLICK_LEN + BLIP_LEN
sound_len       dw CLICK_LEN, BLIP_LEN, BOOM_LEN
; index, red, green, blue, in the DAC's six bits; a zero index ends it.
palette         db FACE, 48, 48, 48, LIGHT, 63, 63, 63, DARK, 32, 32, 32
                db OPEN, 44, 44, 44, DESK, 0, 32, 32, TITLE_BAR, 0, 0, 32, FLAG_RED, 63, 0, 0
                db NUMBER_PEN + 1, 0, 0, 63, NUMBER_PEN + 2, 0, 32, 0, NUMBER_PEN + 3, 63, 0, 0
                db NUMBER_PEN + 4, 0, 0, 32, NUMBER_PEN + 5, 32, 0, 0, NUMBER_PEN + 6, 0, 32, 32
                db NUMBER_PEN + 7, 0, 0, 0, NUMBER_PEN + 8, 32, 32, 32, 0
; The arrow, a row a byte, leftmost pixel in bit 7: its outline in black, its inside in white.
arrow_black     db 0x80, 0xC0, 0xA0, 0x90, 0x88, 0x84, 0x82, 0x9E, 0xA4, 0xD2, 0x12, 0x0C
arrow_white     db 0x00, 0x00, 0x40, 0x60, 0x70, 0x78, 0x7C, 0x60, 0x40, 0x0C, 0x0C, 0x00

msg_ready       db "MINES ready", 0
msg_title_line  db "TITLE", 0
msg_new         db "NEW ", 0
msg_menu_open   db "MENU OPEN", 0
msg_menu_close  db "MENU CLOSE", 0
msg_reveal      db "REVEAL ", 0
msg_flag        db "FLAG ", 0
msg_unflag      db "UNFLAG ", 0
msg_boom        db "BOOM ", 0
msg_win         db "WIN", 0
msg_ok          db "OK", 0
msg_silent      db "NO SOUND", 0
msg_no_vbe      db "MINES needs VBE mode 103h (800 x 600, 256 colours)", 13, 10, "$"
msg_title       db "MINESWEEPER", 0
msg_start       db "Click anywhere to start", 0
msg_how         db "Left click reveals, right click flags, Game opens the menu", 0
msg_esc         db "ESC returns to DOS", 0
msg_game        db "Game", 0
msg_left        db "Mines left:", 0
msg_item_new    db "New game", 0
msg_beginner    db "Beginner", 0
msg_intermediate db "Intermediate", 0
msg_expert      db "Expert", 0
msg_mark        db "*", 0
msg_win_title   db "You win!", 0
msg_win_body    db "Every safe cell is open.", 0
msg_lose_title  db "Boom!", 0
msg_lose_body   db "You stepped on a mine.", 0
msg_ok_button   db "OK", 0

screen          db ON_TITLE
level           db 0
rows            db 0
cols            db 0
board_x         dw 0
board_y         dw 0
total           dw 0
mine_count      dw 0
flags           dw 0
cells_left      dw 0
games           dw 0
lost            db 0
boom_at         dw 0xFFFF
seed            dd 0
sound_on        db 0
sound_phys      dd 0
sound_seg       dw 0
bank            dw 0xFFFF
bank_step       dw 1
win_seg         dw 0xA000
font_off        dw 0
font_seg        dw 0
pointer_x       dw 0
pointer_y       dw 0
pointer_on      db 0
pen             db 0

section .bss
mines           resb MAX_CELLS
cells           resb MAX_CELLS
queue           resw MAX_CELLS
queue_top       resw 1
opened          resw 1
at_row          resb 1
at_col          resb 1
adjacent        resb 1
around_row      resb 1
around_col      resb 1
cell_index      resw 1
cell_x          resw 1
cell_y          resw 1
box             resw 4
fill_w          resd 1
glyph_x         resw 1
glyph_y         resw 1
glyph_bits      resb 1
last_sample     resb 1
number_text     resb 4
under           resb CURSOR_W * CURSOR_H
mode_info       resb 256
