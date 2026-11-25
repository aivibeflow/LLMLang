#if defined(__x86_64__)
.text
.global _start
.global fixture_write
.global fixture_exit
_start:
    andq $-16, %rsp
    call fixture_start
    ud2
fixture_write:
    movq %rsi, %rdx
    movq %rdi, %rsi
    movq $1, %rdi
    movq $1, %rax
    syscall
    ret
fixture_exit:
    movq $60, %rax
    syscall
    ud2
.section .note.GNU-stack,"",%progbits
#else
.text
.global _start
_start:
#if defined(__aarch64__)
    b fixture_start
#elif defined(__riscv)
    tail fixture_start
#endif
#include "../FFI-AGGREGATE-CROSS-ABI-01/syscalls.S"
#endif
