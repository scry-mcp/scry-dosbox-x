; MAPMAIN.ASM -- the resident half of a two-module program written to PRODUCE A MAP.
;
; It is not meant to compute anything: its whole job is to give TLINK three public
; symbols in the resident image and two calls into an OVERLAID module, so the map it
; emits carries a `Publics by Name` section, a `Publics by Value` section printing the
; same set, a "Detailed map of segments" (the section a line-shaped pattern mistakes for
; symbols), and rows both with and without the `idle` mark.
;
; WHAT `idle` MEANS IS NOT KNOWN, and this fixture is half of why.  The reader's own
; docstring said it marks "a public that lives in an overlay TLINK has not made
; resident".  MEASURED on this map, that is backwards: `MAP_OVERLAID_ONE` and
; `MAP_OVERLAID_TWO`, the two publics of the overlaid module, come back with NO mark,
; while the three RESIDENT ones are all flagged.  And measured on the real dos-real16
; map, which has ZERO overlay segments (`:OVY` and `STUBSEG` both absent) and 82 flagged
; symbols, the explanation cannot be about overlays at all -- that file has none.  Two
; publics in ONE segment there, `ATRCT_CHECK_END` and `ATRCT_CICLO_INSERT`, differ in
; the mark, so it is not a property of the segment either.
;
; No replacement explanation is offered, deliberately: swapping one guess for another is
; how the first one got written.  What the reader DOES is unchanged and is not a guess --
; it reads the mark, carries it on the symbol and counts it -- and this fixture pins that
; a map with an overlay in it produces both kinds of row.
;
; WHY THE NAMES ARE UGLY: they are 18 characters, three past the debugger's 15-character
; field, and the two RESIDENT ones share their first 15 -- so the fixture exercises
; truncation AND the collision the disambiguator exists for.
;
; THAT SECOND HALF USED TO BE FALSE. The names were `MAP_RESIDENT_SAME_A` and
; `MAP_RESIDENT_SAME_B`, which shorten to `MAP_RESIDENT_ON` and `MAP_RESIDENT_TW` -- they
; differ at index 13, so all five names in the emitted map shortened to five DISTINCT
; strings and the fixture performed exactly zero disambiguation while its own comment
; said it was the case that proved it. A fixture whose claim about itself is wrong is
; worse than one that claims nothing.
;
; A tidy fixture is where somebody's idea of the input quietly replaces the input.

        .MODEL LARGE
        .STACK 200h

        EXTRN   MAP_OVERLAID_ONE:FAR
        EXTRN   MAP_OVERLAID_TWO:FAR

; `.DATA` COMES BEFORE `.CODE` ON PURPOSE. TASM 3.1 assembles in ONE pass by default,
; so `@DATA` used in the code segment is undefined unless the data segment has already
; been declared. MEASURED: with `.DATA` at the bottom, `**Error** Undefined symbol:
; @DATA`, no .OBJ, and a link that then failed on a missing file.
        .DATA
        PUBLIC  MAP_DATA_SYMBOL
MAP_DATA_SYMBOL DW  0DEADh

        .CODE

        PUBLIC  MAP_RESIDENT_SAME_A
MAP_RESIDENT_SAME_A PROC FAR
        mov     ax, 1
        ret
MAP_RESIDENT_SAME_A ENDP

        PUBLIC  MAP_RESIDENT_SAME_B
MAP_RESIDENT_SAME_B PROC FAR
        mov     ax, 2
        ret
MAP_RESIDENT_SAME_B ENDP

MAPSTART:
; NO `mov ax, @DATA` HERE, and the omission is deliberate rather than sloppy: this
; program is never RUN. What it has to be is a pair of objects TLINK can link into a
; map, and setting DS buys nothing for that while costing a TASM one-pass dependency
; that measurably did not resolve.
        call    MAP_RESIDENT_SAME_A
        call    MAP_RESIDENT_SAME_B
        call    MAP_OVERLAID_ONE
        call    MAP_OVERLAID_TWO
        mov     ax, 4C00h
        int     21h

        END     MAPSTART
