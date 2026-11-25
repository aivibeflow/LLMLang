.option norelax
.text
.global _start
_start:
  la sp, stack_top
  la t0, boot_word
  li t1, 91
  sw t1, 0(t0)
#ifndef OMIT_ZERO
  sw zero, 0(t0)
#endif
  call exercise
  li a0, '!'
  call marker
  li t0, 0x100000
  li t1, 0x5555
  sw t1, 0(t0)
  j .

.global marker
marker:
  li t0, 0x10000000
  sb a0, 0(t0)
  ret
