.syntax unified
.cpu cortex-m3
.thumb

.section .vectors,"a",%progbits
.word __stack_top
.word reset
.rept 14
.word hard_fault
.endr

.section .text.reset,"ax",%progbits
.global reset
.type reset,%function
.thumb_func
reset:
  ldr r0, =__data_load
  ldr r1, =__data_start
  ldr r2, =__data_end
1:
  cmp r1, r2
  bhs 2f
  ldr r3, [r0], #4
  str r3, [r1], #4
  b 1b
2:
  // Test-controlled dirty SRAM makes zeroing observable on every emulator boot.
  ldr r0, =scratch_word
  ldr r1, =0xDEADBEEF
  str r1, [r0]
  ldr r0, =__bss_start
  ldr r1, =__bss_end
  movs r2, #0
3:
  cmp r0, r1
  bhs 4f
  str r2, [r0], #4
  b 3b
4:
  ldr r0, =0x4000C000
  movs r1, #0x60
  str r1, [r0, #0x2c]
  movw r1, #0x0101
  str r1, [r0, #0x30]

  ldr r0, =scratch_word
  ldr r0, [r0]
  cmp r0, #0
  bne failed
  ldr r0, =initial_duty
  ldr r4, [r0]
  cmp r4, #250
  bne failed
  movs r0, #'B'
  bl uart_byte

  ldr r5, =fixture_begin
  ldr r6, =fixture_end
5:
  cmp r5, r6
  bhs done
  ldr r1, [r5], #4
  ldr r2, [r5], #4
  mov r0, r4
  bl step
  mov r4, r0
  movs r0, #' '
  bl uart_byte
  mov r0, r4
  bl output_hex
  b 5b

done:
  movs r0, #'!'
  bl uart_byte
  b halt
failed:
  movs r0, #'X'
  bl uart_byte
halt:
  wfi
  b halt

.type hard_fault,%function
.thumb_func
hard_fault:
  b hard_fault

.type uart_byte,%function
.thumb_func
uart_byte:
  ldr r1, =0x4000C000
6:
  ldr r2, [r1, #0x18]
  tst r2, #0x20
  bne 6b
  str r0, [r1]
  bx lr

.type output_hex,%function
.thumb_func
output_hex:
  push {r4, lr}
  mov r4, r0
  lsrs r0, r4, #4
  bl output_nibble
  and r0, r4, #0xf
  bl output_nibble
  pop {r4, pc}

.type output_nibble,%function
.thumb_func
output_nibble:
  cmp r0, #10
  ite lo
  addlo r0, r0, #'0'
  addhs r0, r0, #('a' - 10)
  b uart_byte

.section .data.initial_duty,"aw",%progbits
.balign 4
initial_duty:
.word 250

.section .bss.scratch_word,"aw",%nobits
.balign 4
scratch_word:
.space 4
