.syntax unified
.cpu cortex-m3
.thumb

.equ SCB_CCR, 0xE000ED14
.equ STKALIGN, 0x200
.ifndef PAINT_WORD
.equ PAINT_WORD, 0xA5A5A5A5
.endif

.section .text.stack_probe,"ax",%progbits
.global stack_paint, stack_watermark, stack_read_handler, stack_read_padding

.type stack_paint,%function
.thumb_func
stack_paint:
  ldr r0, =__stack_top
  sub.w r1, r0, #STACK_WINDOW
  ldr r2, =PAINT_WORD
1:
  str r2, [r1], #4
  cmp r1, r0
  blo 1b
  ldr r0, =SCB_CCR
  ldr r1, [r0]
  orr.w r1, r1, #STKALIGN
  str r1, [r0]
  dsb
  isb
  bx lr

.type stack_watermark,%function
.thumb_func
stack_watermark:
  ldr r2, =__stack_top
  sub.w r1, r2, #STACK_WINDOW
  ldr r3, =PAINT_WORD
  movs r0, #0
2:
  cmp r1, r2
  beq 4f
  ldr.w r12, [r1]
  cmp r12, r3
  bne 3f
  adds r1, #4
  b 2b
3:
  subs r0, r2, r1
4:
  bx lr

.type stack_read_handler,%function
.thumb_func
stack_read_handler:
  ldr r0, =deepest_msp
  ldr r0, [r0]
  cbz r0, 5f
  ldr r1, =__stack_top
  subs r0, r1, r0
5:
  bx lr

.type stack_read_padding,%function
.thumb_func
stack_read_padding:
  ldr r0, =stacked_padding
  ldr r0, [r0]
  bx lr

.section .bss.deepest_msp,"aw",%nobits
.balign 4
.global deepest_msp, stacked_padding
deepest_msp:
.space 4
stacked_padding:
.space 4
