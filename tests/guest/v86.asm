; A guest that runs in virtual-8086 mode, so a stop there has a known answer.
;
; WHY IT EXISTS. The debugger's register pane names the cpu mode at its mode slot, and in VM86
; it says `VM86`: what an EMM386-style memory manager or Windows' enhanced mode leaves a DOS
; program running under. None of the benches this package runs reaches VM86, so this guest
; enters it by itself and stays there, which gives a stop in VM86 a known answer.
;
; WHAT IT DOES. From DOS, flags cleared first (DOS leaves NT set, and an IRET under NT is a task
; return, which ends the emulator with "TSS not busy for IRET"), it builds a GDT (16-bit code
; and data at its own segment's base, a 32-bit handler segment, a 386 TSS whose I/O bitmap lets
; every port below 0x100 through), an IDT of 32 exception gates, enters 16-bit protected mode
; and IRETs into VM86 at a loop that writes `V86 nnnn` lines on port 0xE9, interrupts off so no
; IRQ ever has to be reflected. A fault out of VM86 writes `F` and halts.
;
; ADDRESSES AT A STOP ARE REAL-MODE ONES: CS is the program's own segment, as DOS loaded it.
;
;     nasm -f bin v86.asm -o v86.com
        cpu     386
        org     0x100

start:  cli
        push    word 0x0002             ; NT, IOPL and the rest clear: an IRET under NT is a task return
        popf
        mov     ax, cs
        movzx   eax, ax
        shl     eax, 4                  ; linear base of this segment
        mov     [base], eax
        ; patch the bases of the code, data and TSS descriptors
        mov     ebx, eax
        mov     [gdt_code+2], bx
        mov     [gdt_data+2], bx
        shr     ebx, 16
        mov     [gdt_code+4], bl
        mov     [gdt_data+4], bl
        mov     [gdt_code+7], bh
        mov     [gdt_data+7], bh
        mov     [gdt_c32+2], ax         ; 32-bit handler segment, same base
        mov     ebx, eax
        shr     ebx, 16
        mov     [gdt_c32+4], bl
        mov     [gdt_c32+7], bh
        lea     ebx, [eax + tss]
        mov     [gdt_tss+2], bx
        shr     ebx, 16
        mov     [gdt_tss+4], bl
        mov     [gdt_tss+7], bh
        ; the GDT and IDT registers hold linear addresses
        lea     ebx, [eax + gdt]
        mov     [gdtr+2], ebx
        lea     ebx, [eax + idt]
        mov     [idtr+2], ebx
        ; 32 exception gates, all to `fault`, through the 32-bit handler segment
        mov     di, idt
        mov     cx, 32
.gate:  mov     word [di], fault
        mov     word [di+2], SEL_C32
        mov     word [di+4], 0x8E00     ; present, DPL 0, 386 interrupt gate
        mov     word [di+6], 0
        add     di, 8
        loop    .gate
        ; the TSS: ring-0 stack for an exception out of VM86
        mov     dword [tss+4], stack0_top
        mov     word [tss+8], SEL_DATA
        mov     word [tss+102], iomap - tss
        mov     [vm_seg], cs
        lgdt    [gdtr]
        lidt    [idtr]
        mov     eax, cr0
        or      al, 1
        mov     cr0, eax
        jmp     SEL_CODE:pm
pm:     mov     ax, SEL_DATA
        mov     ds, ax
        mov     es, ax
        mov     ss, ax
        mov     sp, stack0_top
        mov     ax, SEL_TSS
        ltr     ax
        movzx   eax, word [vm_seg]
        push    eax                     ; GS
        push    eax                     ; FS
        push    eax                     ; DS
        push    eax                     ; ES
        push    eax                     ; SS
        push    dword vm_stack_top      ; ESP
        push    dword 0x00023002        ; EFLAGS: VM, IOPL 3, IF clear
        push    eax                     ; CS
        push    dword v86loop           ; EIP
        o32 iret

; ------------------------------------------------------------------ virtual-8086 mode
v86loop:
        mov     si, msg
.out:   lodsb
        test    al, al
        jz      .count
        out     0xE9, al
        jmp     .out
.count: mov     bx, digits + 3          ; ASCII odometer, as probe.asm keeps
.inc:   inc     byte [bx]
        cmp     byte [bx], '9'
        jbe     .wait
        mov     byte [bx], '0'
        dec     bx
        cmp     bx, digits
        jae     .inc
.wait:  mov     dx, 200
.w1:    mov     cx, 0
.w2:    loop    .w2
        dec     dx
        jnz     .w1
        jmp     v86loop

; ------------------------------------------------------------------ a fault, from VM86
        bits    32
fault:  mov     dx, 0xE9
        mov     al, 'F'
        out     dx, al
.h:     hlt
        jmp     .h
        bits    16

msg:    db      "V86 "
digits: db      "0000", 10, 0
base:   dd      0
vm_seg: dw      0

SEL_CODE equ gdt_code - gdt
SEL_DATA equ gdt_data - gdt
SEL_TSS  equ gdt_tss - gdt
SEL_C32  equ gdt_c32 - gdt

        align   8
gdt:    dq      0
gdt_code: dw    0xFFFF, 0
          db    0, 0x9A, 0x00, 0        ; 16-bit code, ring 0
gdt_data: dw    0xFFFF, 0
          db    0, 0x92, 0x00, 0        ; 16-bit data
gdt_tss:  dw    tss_end - tss - 1, 0
          db    0, 0x89, 0x00, 0        ; available 386 TSS
gdt_c32:  dw    0xFFFF, 0
          db    0, 0x9A, 0x40, 0        ; 32-bit code for the fault handler
gdt_end:
gdtr:   dw      gdt_end - gdt - 1
        dd      0
idtr:   dw      32 * 8 - 1
        dd      0

        align   8
idt:    times   32 * 8 db 0

        align   4
tss:    times   104 db 0
iomap:  times   (0x100 / 8) db 0        ; ports 0x00-0xFF all allowed
        db      0xFF
tss_end:

        align   16
        times   256 db 0
stack0_top:
        times   256 db 0
vm_stack_top:
