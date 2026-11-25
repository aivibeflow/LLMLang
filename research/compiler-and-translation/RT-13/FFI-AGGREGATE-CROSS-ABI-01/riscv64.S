.text
.global _start
_start:
    la s0, input_vectors
    la s1, input_end
    la s2, output
    mv s3, s2
1:
    li t0, 0x3fe0000000000000
    fmv.d.x fa0, t0
    li a1, 0x1234
#if defined(HARD_FLOAT) ^ defined(WRONG_MIXED)
    fld fa0, 0(s0)
    ld a0, 8(s0)
    call fixture_mixed
    fsd fa0, 0(s3)
    sd a0, 8(s3)
#else
    ld a0, 0(s0)
    ld a1, 8(s0)
    call fixture_mixed
    sd a0, 0(s3)
    sd a1, 8(s3)
#endif
#if defined(HARD_FLOAT)
    fld fa0, 16(s0)
    fld fa1, 24(s0)
    call fixture_floats
    fsd fa0, 16(s3)
    fsd fa1, 24(s3)
#else
    ld a0, 16(s0)
    ld a1, 24(s0)
    call fixture_floats
    sd a0, 16(s3)
    sd a1, 24(s3)
#endif

    addi a0, s3, 32
    ld a1, 32(s0)
    ld a2, 40(s0)
    call fixture_wide

    addi s0, s0, 48
    addi s3, s3, 56
    bltu s0, s1, 1b
    mv a0, s2
    sub s4, s3, s2
    mv a1, s4
    call fixture_write
    xor a0, a0, s4
    snez a0, a0
    call fixture_exit
.bss
.p2align 3
output: .skip 1792
.section .note.GNU-stack,"",%progbits
