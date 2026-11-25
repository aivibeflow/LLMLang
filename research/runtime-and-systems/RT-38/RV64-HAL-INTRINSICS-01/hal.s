.text
.p2align 2
.globl read_sp
.type read_sp,@function
read_sp:
  mv a0, sp
  ret
.size read_sp, .-read_sp

.globl memory_barrier
.type memory_barrier,@function
memory_barrier:
  fence rw, rw
  ret
.size memory_barrier, .-memory_barrier

.globl translation_barrier
.type translation_barrier,@function
translation_barrier:
  sfence.vma
  ret
.size translation_barrier, .-translation_barrier
