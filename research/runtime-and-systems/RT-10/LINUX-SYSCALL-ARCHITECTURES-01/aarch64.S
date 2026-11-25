.text
.globl _start
.type _start,%function
_start:
    bl run_contract
    mov x8, #93
    svc #0
    brk #0

.globl raw_read
.type raw_read,%function
raw_read:
    mov x8, #63
    svc #0
    ret

.globl raw_write
.type raw_write,%function
raw_write:
    mov x8, #64
    svc #0
    ret

.section .note.GNU-stack,"",%progbits
