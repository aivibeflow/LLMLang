.text
.global manual_call
manual_call:
#if defined(__aarch64__)
    mov x9, x1
    ldr w1, [x9]
    ldr w2, [x9, #8]
    ldr x3, [x9, #32]
#if defined(WRONG_FLOAT)
    ldr x4, [x9, #24]
    fmov d0, #0.5
#else
    ldr d0, [x9, #24]
#endif
    b fixture_var
#elif defined(__riscv)
    mv t0, a1
    lw a1, 0(t0)
    lw a2, 8(t0)
    ld a4, 32(t0)
#if defined(WRONG_FLOAT)
    fld fa0, 24(t0)
    li a3, 0x3fe0000000000000
#else
    ld a3, 24(t0)
#endif
    tail fixture_var
#elif defined(MS_ABI)
    subq $40, %rsp
    movq %rdi, %rcx
    movl 0(%rsi), %edx
    movl 8(%rsi), %r8d
    movq 24(%rsi), %r9
    movq %r9, %xmm3
#if defined(WRONG_FLOAT)
    movabsq $0x3fe0000000000000, %r9
#endif
    movq 32(%rsi), %rax
    movq %rax, 32(%rsp)
    call fixture_var
    addq $40, %rsp
    ret
#elif defined(__x86_64__)
    movq %rsi, %r8
    movl 0(%r8), %esi
    movl 8(%r8), %edx
    movq 32(%r8), %rcx
#if defined(WRONG_FLOAT)
    movq 24(%r8), %r9
    movabsq $0x3fe0000000000000, %rax
    movq %rax, %xmm0
#else
    movq 24(%r8), %xmm0
#endif
    movl $1, %eax
    jmp fixture_var
#endif
.section .note.GNU-stack,"",%progbits
