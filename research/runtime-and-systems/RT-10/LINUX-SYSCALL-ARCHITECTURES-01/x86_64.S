.text
.globl _start
.type _start,@function
_start:
    andq $-16, %rsp
    call run_contract
    movl %eax, %edi
    movl $60, %eax
    syscall
    ud2

.globl raw_read
.type raw_read,@function
raw_read:
    xorl %eax, %eax
    syscall
    ret

.globl raw_write
.type raw_write,@function
raw_write:
    movl $1, %eax
    syscall
    ret

.section .note.GNU-stack,"",@progbits
