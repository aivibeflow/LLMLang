.syntax unified
.cpu cortex-m3
.thumb

.macro function name
  .balign 32
  .global \name
  .type \name,%function
  .thumb_func
\name:
.endm

.macro end_function name
  .size \name, .-\name
.endm

.section .vectors,"a",%progbits
.word __stack_top
.word reset
.rept 13
.word reset
.endr
.word timer_interrupt

.section .text.handlers,"ax",%progbits
function reset
  b reset
end_function reset

function timer_interrupt
  push {r4, lr}
  bl delegate
  pop {r4, pc}
end_function timer_interrupt

function delegate
.if CASE == 1
  b.w tail_adapter
.else
  push {r4, lr}
.if CASE == 2
  bl wait_leaf
.elseif CASE == 3
  bl reserve_slice
.elseif CASE == 4
  blx r0
.elseif CASE == 5
  mov r4, r0
  bl wait_leaf
  blx r4
.else
  bl ack_pending
.endif
  pop {r4, pc}
.endif
end_function delegate

function tail_adapter
  b.w ack_pending
end_function tail_adapter

function ack_pending
  movw r0, #0xed04
  movt r0, #0xe000
.if CASE == 6
  mov.w r1, #(1 << 26)
.else
  mov.w r1, #(1 << 25)
.endif
  str r1, [r0]
  bx lr
end_function ack_pending

function wait_leaf
  wfi
  bx lr
end_function wait_leaf

function reserve_slice
  movw r1, :lower16:bump_head
  movt r1, :upper16:bump_head
  ldr r0, [r1]
  adds r2, r0, #4
  str r2, [r1]
  bx lr
end_function reserve_slice

.section .bss.bump_head,"aw",%nobits
.balign 4
bump_head:
.space 4
