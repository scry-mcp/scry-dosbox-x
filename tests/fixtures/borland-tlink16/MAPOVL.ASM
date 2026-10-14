; MAPOVL.ASM -- the OVERLAID half, linked with TLINK's `/o`.
;
; IT EXISTS TO PUT AN OVERLAY IN THE MAP, which is what gives the fixture the `:OVY` and
; `STUBSEG` segment classes and the two publics that come back with NO mark beside them.
;
; It does NOT exist to produce the `idle` rows, which is what this comment used to claim
; and what MEASURING it disproved: the flagged symbols in the emitted map are the three
; RESIDENT ones, and these two are the plain rows.  The finding is written up in
; MAPMAIN.ASM's header, where the fixture's shape is explained.

        .MODEL LARGE

        .CODE

        PUBLIC  MAP_OVERLAID_ONE
MAP_OVERLAID_ONE PROC FAR
        mov     bx, 11h
        ret
MAP_OVERLAID_ONE ENDP

        PUBLIC  MAP_OVERLAID_TWO
MAP_OVERLAID_TWO PROC FAR
        mov     bx, 22h
        ret
MAP_OVERLAID_TWO ENDP

        END
