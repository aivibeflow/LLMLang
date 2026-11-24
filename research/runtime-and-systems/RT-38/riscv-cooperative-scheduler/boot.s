.option norvc
.option norelax
.equ UART, 0x10000000
.equ TEST_EXIT, 0x00100000

.macro save reg, number
  sd \reg, (8 * \number)(sp)
.endm
.macro restore reg, number
  ld \reg, (8 * \number)(sp)
.endm

.section .text.boot,"ax",@progbits
.global _start
_start:
  csrw mie, zero
  csrw medeleg, zero
  csrw mideleg, zero
  csrw satp, zero
  sfence.vma zero, zero
  la t0, trap
  csrw mtvec, t0
  la t0, user_entry
  srli t0, t0, 2
  csrw pmpaddr0, t0
  la t0, stack_a
  srli t0, t0, 2
  csrw pmpaddr1, t0
  la t0, stack_b_top
  srli t0, t0, 2
  csrw pmpaddr2, t0
  li t0, 0xb0d00
  csrw pmpcfg0, t0
  csrr t1, pmpcfg0
  bne t0, t1, fail
  csrr t0, mstatus
  li t1, ((3 << 11) | (1 << 17))
  not t1, t1
  and t0, t0, t1
  csrw mstatus, t0
  la sp, context_a
  la t0, user_entry
  sd t0, 0(sp)
  la t0, stack_a_top
  sd t0, 16(sp)
  li t0, WORK_A
  sd t0, 96(sp)                   // x12/a2 holds the worker's yield budget.
  la t0, context_b
  la t1, user_entry
  sd t1, 0(t0)
  la t1, stack_b_top
  sd t1, 16(t0)
  li t1, 1
  sd t1, 88(t0)                   // x11/a1 holds the initial task ID.
  li t1, WORK_B
  sd t1, 96(t0)
  j resume

.balign 16
.global trap
trap:
  csrrw sp, mscratch, sp
  save ra, 1
  save gp, 3
  save tp, 4
  save t0, 5
  save t1, 6
  save t2, 7
  save s0, 8
  save s1, 9
  save a0, 10
  save a1, 11
  save a2, 12
  save a3, 13
  save a4, 14
  save a5, 15
  save a6, 16
  save a7, 17
  save s2, 18
  save s3, 19
  save s4, 20
  save s5, 21
  save s6, 22
  save s7, 23
  save s8, 24
  save s9, 25
  save s10, 26
  save s11, 27
  save t3, 28
  save t4, 29
  save t5, 30
  save t6, 31
  csrr t0, mscratch
  save t0, 2
  csrr t0, mepc
  save t0, 0
  csrr t0, mstatus
  srli t0, t0, 11
  andi t0, t0, 3
  bnez t0, fail
  csrr t0, mcause
  li t1, 8
  bne t0, t1, fail

  la t0, context_a
  bne sp, t0, trapped_b
  la s2, context_b
  la s3, completed_a
  la s4, completed_b
  la s5, yielded_a
  li s6, 'A'
  bnez a1, fail
  j trapped
trapped_b:
  la t0, context_b
  bne sp, t0, fail
  la s2, context_a
  la s3, completed_b
  la s4, completed_a
  la s5, yielded_b
  li s6, 'B'
  li t0, 1
  bne a1, t0, fail
trapped:
  li t0, 2
  beq a7, t0, stopping
  li t0, 1
  bne a7, t0, report_user_fault
  la t0, user_yield
  ld t1, 0(sp)
  bne t0, t1, fail
  ld t2, 0(s5)
  addi t2, t2, 1
  bne t2, a0, replayed
  bgtu t2, a2, fail
  sd t2, 0(s5)
.if POLICY != 4
  addi t1, t1, 4
.endif
  sd t1, 0(sp)
  mv a0, s6
  call uart
.if POLICY == 1
  j resume
.else
  ld t0, 0(s4)
  bnez t0, resume
  mv sp, s2
  j resume
.endif

stopping:
  la t0, user_stop
  ld t1, 0(sp)
  bne t0, t1, fail
  ld t0, 0(s5)
  bne t0, a2, fail
  li t0, 1
  sd t0, 0(s3)
  addi a0, s6, 32
  call uart
  ld t0, 0(s4)
  bnez t0, complete
  mv sp, s2
  j resume

resume:
  restore t0, 0
  csrw mepc, t0
  restore t1, 2
.if POLICY == 3
  la t2, user_entry
  beq t0, t2, resume_stack
  la t2, context_a
  beq sp, t2, wrong_stack_a
  ld t1, 16(t2)
  j resume_stack
wrong_stack_a:
  la t2, context_b
  ld t1, 16(t2)
resume_stack:
.endif
  csrw mscratch, t1
  restore ra, 1
  restore gp, 3
  restore tp, 4
  restore t0, 5
  restore t1, 6
  restore t2, 7
  restore s0, 8
.if POLICY == 2
  li s0, 0
.endif
  restore s1, 9
  restore a0, 10
  restore a1, 11
  restore a2, 12
  restore a3, 13
  restore a4, 14
  restore a5, 15
  restore a6, 16
  restore a7, 17
  restore s2, 18
  restore s3, 19
  restore s4, 20
  restore s5, 21
  restore s6, 22
  restore s7, 23
  restore s8, 24
  restore s9, 25
  restore s10, 26
  restore s11, 27
  restore t3, 28
  restore t4, 29
  restore t5, 30
  restore t6, 31
  csrrw sp, mscratch, sp
  mret

report_user_fault:
  la t0, fault_ecall
  ld t1, 0(sp)
  bne t0, t1, fail
  li t0, 241
  beq a7, t0, saved_register_fault
  li t0, 242
  beq a7, t0, stack_fault
  li t0, 243
  bne a7, t0, fail
  li a0, 'T'
  j report_fault
saved_register_fault:
  li a0, 'S'
  j report_fault
stack_fault:
  li a0, 'K'
  j report_fault
replayed:
  li a0, 'P'
report_fault:
  call uart
  j poweroff
fail:
  li a0, 'X'
  call uart
  j poweroff
complete:
  li a0, '!'
  call uart
poweroff:
  li t0, TEST_EXIT
  li t1, 0x5555
  sw t1, 0(t0)
  j .
uart:
  li t0, UART
1:
  lbu t1, 5(t0)
  andi t1, t1, 0x20
  beqz t1, 1b
  sb a0, 0(t0)
  ret

.section .user.text,"ax",@progbits
.global user_entry, user_yield, user_stop
user_entry:
  addi sp, sp, -16
  addi s0, a1, 100
  addi t3, a1, 200
  sd s0, 0(sp)
worker:
  addi s1, s1, 1
  mv a0, s1
  li a7, 1
user_yield:
  ecall
  addi t0, a1, 100
  bne s0, t0, bad_saved
  ld t1, 0(sp)
  bne t1, t0, bad_stack
  addi t0, a1, 200
  bne t3, t0, bad_t3
  bne s1, a2, worker
  li a7, 2
user_stop:
  ecall
  j .
bad_saved:
  li a7, 241
  j fault_ecall
bad_stack:
  li a7, 242
  j fault_ecall
bad_t3:
  li a7, 243
fault_ecall:
  ecall
  j .

.section .bss.kernel,"aw",@nobits
.balign 256
context_a: .space 256
context_b: .space 256
yielded_a: .space 8
yielded_b: .space 8
completed_a: .space 8
completed_b: .space 8

.section .user.stack,"aw",@nobits
.balign 4096
stack_a: .space 4096
stack_a_top:
stack_b: .space 4096
stack_b_top:
