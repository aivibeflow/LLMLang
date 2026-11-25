.section .text.start,"ax"
.global _start
.type _start,@function
_start:
  la sp, boot_stack_top
  call read_sp
  call memory_barrier
  call translation_barrier
1:
  j 1b
.size _start, .-_start

.section .bss.stack,"aw",@nobits
.p2align 4
.space 4096
boot_stack_top:
