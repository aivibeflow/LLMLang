.syntax unified
.cpu cortex-m3
.thumb

.equ UART0, 0x4000C000
.equ SYSTICK, 0xE000E010

.section .vectors,"a",%progbits
.word __stack_top
.word reset
.rept 14
.word failed
.endr

.section .text.reset,"ax",%progbits
.global reset
.type reset,%function
.thumb_func
reset:
  ldr r0, =UART0
  movs r1, #0x60
  str r1, [r0, #0x2c]
  movw r1, #0x0101
  str r1, [r0, #0x30]
  movs r0, #'B'
  bl uart_byte

  ldr r4, =SYSTICK
  movs r1, #0
  str r1, [r4]
  movs r1, #63
  str r1, [r4, #4]
  movs r1, #0
  str r1, [r4, #8]
  movs r1, #5           // Enable processor-clock counting with TICKINT clear.
  str r1, [r4]
  movw r3, #16384
1:
  subs r3, #1
  bne 1b
  movs r1, #4           // Disarm without consuming the latched COUNTFLAG.
  str r1, [r4]
  dsb
.ifdef RESET_AFTER_LATCH
  movw r1, #0x1234
  str r1, [r4, #8]      // Any write to VAL clears the current count and COUNTFLAG.
  dsb
  ldr r1, [r4, #8]
  cbnz r1, failed
.endif
  mov r0, r4
  bl sample_pair
  ldr r1, =last_sample
  str r0, [r1]
  ldr r4, [r1]
  cmp r4, #3
  bhi failed
  lsrs r0, r4, #1
  adds r0, #'0'
  bl uart_byte
  and r0, r4, #1
  adds r0, #'0'
  bl uart_byte
  movs r0, #'!'
  bl uart_byte
  b halt

.type failed,%function
.thumb_func
failed:
  movs r0, #'X'
  bl uart_byte
halt:
  b halt

.type uart_byte,%function
.thumb_func
uart_byte:
  ldr r1, =UART0
2:
  ldr r2, [r1, #0x18]
  tst r2, #0x20
  bne 2b
  str r0, [r1]
  bx lr

.section .bss.last_sample,"aw",%nobits
.balign 4
last_sample:
.space 4
