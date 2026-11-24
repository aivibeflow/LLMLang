.option norvc
.option norelax

.equ UART, 0x10000000
.equ TEST_EXIT, 0x00100000
.equ USER_VA, 0x40000000
.equ USER_STACK_TOP_VA, 0x40002000
.equ PROTECTED_VA, 0x40400000
.equ PRIVATE_VALUE, 0x1234abcd
.set PAGED, (PROFILE == 2 || PROFILE == 3)

.macro pte table, displacement, target, flags
  la t0, \table
  la t1, \target
  srli t1, t1, 12
  slli t1, t1, 10
  ori t1, t1, \flags
  sd t1, \displacement(t0)
.endm

.section .text.boot,"ax",@progbits
.balign 16
.global _start
.type _start,@function
_start:
  csrw mie, zero
  csrw medeleg, zero
  csrw mideleg, zero
  la sp, machine_stack_top
  csrw mscratch, sp
  la t0, trap
  csrw mtvec, t0
  la t0, protected_word
  ld t1, 0(t0)
  li t2, PRIVATE_VALUE
  bne t1, t2, fail
  li a0, 'B'
  call uart_byte

.if PROFILE == 1 || PROFILE == 4
  la t0, user_entry
  srli t0, t0, 2
  csrw pmpaddr0, t0
.if PROFILE == 4
  la t0, user_stack
  srli t0, t0, 2
  csrw pmpaddr1, t0
  la t0, user_stack_top
  srli t0, t0, 2
  csrw pmpaddr2, t0
  li t0, 0xb0d00        // Separate TOR regions: user code RX and stack RW.
.else
  la t0, user_stack_top
  srli t0, t0, 2
  csrw pmpaddr1, t0
  li t0, 0xf00          // Entry 0 OFF, entry 1 TOR with R/W/X.
.endif
.else
  li t0, -1
  csrw pmpaddr0, t0
  li t0, 0xf            // Broad physical aperture. Sv39 supplies page policy.
.endif
  csrw pmpcfg0, t0
  csrr t1, pmpcfg0
  bne t0, t1, fail

.if PAGED
  la t0, root_table
  la t1, page_tables_end
1:
  sd zero, 0(t0)
  addi t0, t0, 8
  bltu t0, t1, 1b
  pte root_table, 8, directory, 1
  pte directory, 0, user_leaves, 1
  pte directory, 16, protected_leaves, 1
  pte user_leaves, 0, user_entry, 0x5b    // V/R/X/U/A.
  pte user_leaves, 8, user_stack, 0xd7    // V/R/W/U/A/D.
.if PROFILE == 3
  pte protected_leaves, 0, protected_word, 0x53  // Control: V/R/U/A.
.else
  pte protected_leaves, 0, protected_word, 0x43  // V/R/A, U clear.
.endif
  la t0, root_table
  srli t0, t0, 12
  li t1, (8 << 60)       // Sv39, ASID 0.
  or t0, t0, t1
  fence rw, rw
  csrw satp, t0
  sfence.vma zero, zero
  csrr t1, satp
  bne t0, t1, fail
  li t0, USER_VA
  li a2, PROTECTED_VA
  li sp, USER_STACK_TOP_VA
.else
  csrw satp, zero
  sfence.vma zero, zero
  la t0, user_entry
  la a2, protected_word
  la sp, user_stack_top
.endif
  csrw mepc, t0
  csrr t0, mstatus
  li t1, ((3 << 11) | (1 << 17)) // Clear MPP to U-mode and MPRV to zero.
  not t1, t1
  and t0, t0, t1
  csrw mstatus, t0
  mret

.section .text.trap,"ax",@progbits
.balign 16
.global trap
.type trap,@function
trap:
  csrrw sp, mscratch, sp
  addi sp, sp, -48
  sd t0, 0(sp)
  sd t1, 8(sp)
  sd t2, 16(sp)
  sd t3, 24(sp)
  sd ra, 32(sp)
  sd a0, 40(sp)
  csrr t0, mstatus
  srli t0, t0, 11
  andi t0, t0, 3
  bnez t0, fail                  // Every admitted trap originates from U-mode.
  csrr t0, mcause
  li t1, 8
  beq t0, t1, syscall
  li t1, 13
  beq t0, t1, page_fault
  li t1, 15
  beq t0, t1, store_page_fault
  li t1, 7
  beq t0, t1, store_access_fault
  li t1, 5
  bne t0, t1, fail
  li a0, 'F'
  j load_fault
page_fault:
  li a0, 'P'
load_fault:
  csrr t2, mtval
  bne t2, a2, fail
  la t2, user_probe
  j check_probe_pc
store_page_fault:
  li a0, 'S'
  j store_fault
store_access_fault:
  li a0, 'T'
store_fault:
  csrr t2, mtval
  ld t3, 0(sp)                   // User t0 retains the attempted pointer.
  bne t2, t3, fail
  la t2, user_store
check_probe_pc:
.if PAGED
  la t3, user_entry
  sub t2, t2, t3
  li t3, USER_VA
  add t2, t2, t3
.endif
  csrr t3, mepc
  bne t2, t3, fail
  sd zero, 40(sp)                 // Explicit fallback for the rejected load.
  call uart_byte
  j resume_user

syscall:
  li t0, 1
  beq a7, t0, entered
  li t0, 2
  beq a7, t0, report_value
  li t0, 3
  beq a7, t0, finish
  li t0, 4
  beq a7, t0, report_store
  li t0, 99
  bne a7, t0, fail
  li t0, -38                    // ENOSYS for the fixture's invalid request.
  sd t0, 40(sp)
  li a0, 'I'
  call uart_byte
  j resume_user
entered:
  li a0, 'E'
  call uart_byte
  j resume_user
report_value:
  ld t0, 40(sp)
  li t1, PRIVATE_VALUE
  beq t0, t1, visible
  bnez t0, fail
  li a0, 'Z'
  j report_byte
visible:
  li a0, 'V'
report_byte:
  call uart_byte
  j resume_user
report_store:
  ld t0, 40(sp)
  li a0, 'R'
  beqz t0, report_byte
  li t1, 1
  bne t0, t1, fail
  li a0, 'W'
  j report_byte
resume_user:
  csrr t0, mepc
  addi t0, t0, 4                // The fixture uses only four-byte instructions.
  csrw mepc, t0
  ld t0, 0(sp)
  ld t1, 8(sp)
  ld t2, 16(sp)
  ld t3, 24(sp)
  ld ra, 32(sp)
  ld a0, 40(sp)
  addi sp, sp, 48
  csrrw sp, mscratch, sp
  mret

finish:
  li a0, '!'
  call uart_byte
  li t0, TEST_EXIT
  li t1, 0x5555
  sw t1, 0(t0)
  j .
fail:
  li a0, 'X'
  call uart_byte
  li t0, TEST_EXIT
  li t1, 0x3333
  sw t1, 0(t0)
  j .

uart_byte:
  li t0, UART
2:
  lbu t1, 5(t0)
  andi t1, t1, 0x20
  beqz t1, 2b
  sb a0, 0(t0)
  ret

.section .user.text,"ax",@progbits
.balign 16
.global user_entry, user_probe, user_store
user_entry:
  addi sp, sp, -16
  li t0, 42
  sd t0, 0(sp)
  ld t1, 0(sp)
  bne t0, t1, user_fail
  addi sp, sp, 16
  li a7, 1
  ecall
  li a7, 99
  ecall
  li t0, -38
  bne a0, t0, user_fail
  la t0, user_rx_marker
  ld t1, 0(t0)
  li a0, 1
user_store:
  sd t1, 0(t0)                  // Restore the same marker bytes if writable.
  li a7, 4
  ecall
user_probe:
  ld a0, 0(a2)
  li a7, 2
  ecall
  li a7, 3
  ecall
user_fail:
  li a7, 255
  ecall
  j .
.balign 8
user_rx_marker:
.quad 0x51525354

.section .bss.kernel,"aw",@nobits
.balign 4096
.if PAGED
root_table:
.space 4096
directory:
.space 4096
user_leaves:
.space 4096
protected_leaves:
.space 4096
page_tables_end:
.endif
machine_stack:
.space 4096
machine_stack_top:

.section .user.stack,"aw",@nobits
.balign 4096
user_stack:
.space 4096
user_stack_top:

.section .data.protected,"aw",@progbits
.balign 4096
.global protected_word
protected_word:
.quad PRIVATE_VALUE
