.text
.global fixture_write
.global fixture_exit
#if defined(__aarch64__)
fixture_write:
    mov x2, x1
    mov x1, x0
    mov x0, #1
    mov x8, #64
    svc #0
    ret
fixture_exit:
    mov x8, #93
    svc #0
    brk #0
#elif defined(__riscv)
fixture_write:
    mv a2, a1
    mv a1, a0
    li a0, 1
    li a7, 64
    ecall
    ret
fixture_exit:
    li a7, 93
    ecall
    ebreak
#endif
.section .note.GNU-stack,"",%progbits
