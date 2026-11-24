.option norvc
.option norelax
.equ UART, 0x10000000
.equ TEST_EXIT, 0x00100000

.section .text.boot,"ax",@progbits
.global _start
_start:
  csrr s0, mhartid
  la t0, trap
  csrw mtvec, t0
  csrw mie, zero
  li t0, 1
  bgtu s0, t0, trap
  la sp, stack_top
  slli t0, s0, 12
  sub sp, sp, t0
  la s1, arena
  la s2, state

  // Make both harts reach the call boundary before either RMW starts.
  slli s3, s0, 2
  add t1, s2, s3
  li t0, 1
  sw t0, 0(t1)
  fence rw, rw
wait_ready:
  lw t0, 0(s2)
  lw t1, 4(s2)
  and t0, t0, t1
  beqz t0, wait_ready
  fence r, rw

  addi a0, s1, 1
  li a1, 1
  call inc_acqrel
  andi a0, a0, 255
  add t0, s2, s3
  sw a0, 8(t0)
  beqz s0, publisher

subscriber:
  addi a0, s1, 5
  addi a1, s1, 4
  call read_fence
  srli t0, a0, 8
  andi t0, t0, 255
  beqz t0, subscriber
  li t0, 0x12a
  slli a0, a0, 48
  srli a0, a0, 48
  bne a0, t0, trap
  li t0, 1
  fence rw, w
  sw t0, 16(s2)
hold:
  wfi
  j hold

publisher:
  addi a0, s1, 4
  addi a1, s1, 5
  li a2, 42
  call publish_fence
wait_result:
  lw t0, 16(s2)
  beqz t0, wait_result
  fence r, rw

  lw t0, 8(s2)
  lw t1, 12(s2)
  beq t0, t1, trap
  add t0, t0, t1
  li t1, 509
  bne t0, t1, trap
  lw t0, 0(s1)
  li t1, 0x5aff00c7
  bne t0, t1, trap

  addi a0, s1, 8
  li a1, 1
  call inc_word
  addiw a0, a0, 1
  bnez a0, trap
  lw t0, 8(s1)
  bnez t0, trap
  li a0, 'R'
  call emit
  li a0, '!'
  j finish
trap:
  li a0, 'X'
finish:
  call emit
  li t0, TEST_EXIT
  li t1, 0x5555
  sw t1, 0(t0)
  j hold
emit:
  li t0, UART
1:
  lbu t1, 5(t0)
  andi t1, t1, 0x20
  beqz t1, 1b
  sb a0, 0(t0)
  ret

.section .data,"aw",@progbits
.balign 4
arena:
.word 0x5afffec7
.byte 0, 0, 0, 0
.word 0xffffffff

.section .bss,"aw",@nobits
.balign 16
state: .space 32
.space 8192
stack_top:
