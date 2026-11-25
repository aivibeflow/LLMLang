.text
.global _start
_start:
    adrp x19, input_vectors
    add x19, x19, :lo12:input_vectors
    adrp x20, input_end
    add x20, x20, :lo12:input_end
    adrp x21, output
    add x21, x21, :lo12:output
    mov x22, x21
1:
    ldp x9, x10, [x19]
#if defined(WRONG_MIXED)
    fmov d0, x9
    mov x0, x10
    mov x1, #0x1234
    bl fixture_mixed
    mov x1, x0
    fmov x0, d0
#else
    mov x0, x9
    mov x1, x10
    bl fixture_mixed
#endif
    stp x0, x1, [x22]

    ldp d0, d1, [x19, #16]
    bl fixture_floats
    stp d0, d1, [x22, #16]

    ldp x0, x1, [x19, #32]
    add x8, x22, #32
    bl fixture_wide

    add x19, x19, #48
    add x22, x22, #56
    cmp x19, x20
    b.lo 1b
    mov x0, x21
    sub x23, x22, x21
    mov x1, x23
    bl fixture_write
    cmp x0, x23
    cset x0, ne
    bl fixture_exit
.bss
.p2align 3
output: .skip 1792
.section .note.GNU-stack,"",%progbits
