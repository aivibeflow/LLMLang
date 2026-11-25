.text
.globl _start
.type _start,@function
_start:
    call run_contract
    li a7, 93
    ecall
    unimp

.globl raw_read
.type raw_read,@function
raw_read:
    li a7, 63
    ecall
    ret

.globl raw_write
.type raw_write,@function
raw_write:
    li a7, 64
    ecall
    ret

.section .note.GNU-stack,"",@progbits
