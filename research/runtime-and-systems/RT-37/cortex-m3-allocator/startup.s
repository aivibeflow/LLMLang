.syntax unified
.cpu cortex-m3
.thumb

.equ UART0, 0x4000C000

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
  ldr r0, =arena
  tst r0, #63
  bne failed
  ldr r1, =arena_end
  subs r1, r1, r0
  cmp r1, #64
  bne failed
  movs r0, #'B'
  bl uart_byte
  ldr r5, =request_begin
  ldr r6, =request_end
1:
  cmp r5, r6
  beq complete
  ldr r3, [r5], #4
  ldr r1, [r5], #4
  ldr r2, [r5], #4
  ldr r0, =cursor
  cbz r3, set_cursor
  bl reserve_request
  cmp r0, #64
  bls 2f
  cmn r0, #1
  bne failed
2:
  bl hex32
  ldr r0, =cursor
  ldr r0, [r0]
  bl hex32
  b 1b
set_cursor:
  str r1, [r0]
  movs r0, #'|'
  bl uart_byte
  b 1b
complete:
  movs r0, #'!'
  bl uart_byte
  b halt

.type failed,%function
.thumb_func
failed:
  movs r0, #'X'
  bl uart_byte
halt:
  wfi
  b halt

.type hex32,%function
.thumb_func
hex32:
  push {r4, r5, r6, lr}
  mov r4, r0
  movs r5, #28
3:
  lsr.w r0, r4, r5
  and r0, r0, #15
  cmp r0, #10
  ite lo
  addlo r0, r0, #'0'
  addhs r0, r0, #('a' - 10)
  bl uart_byte
  subs r5, #4
  bpl 3b
  pop {r4, r5, r6, pc}

.type uart_byte,%function
.thumb_func
uart_byte:
  ldr r1, =UART0
4:
  ldr r2, [r1, #0x18]
  tst r2, #0x20
  bne 4b
  str r0, [r1]
  bx lr

.section .bss.arena,"aw",%nobits
.balign 64
.global arena, arena_end
arena:
  .space 64
arena_end:

.section .bss.cursor,"aw",%nobits
.balign 4
.global cursor
cursor:
  .space 4
