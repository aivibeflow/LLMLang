.section .note.llmlang,"a",@note
.balign 4
.long 8, payload_end - payload, 0x4c4c4d01
.asciz "LLMLANG"
.balign 4
payload:
.incbin "contracts.json"
payload_end:
.balign 4
.section .note.GNU-stack,"",@progbits
