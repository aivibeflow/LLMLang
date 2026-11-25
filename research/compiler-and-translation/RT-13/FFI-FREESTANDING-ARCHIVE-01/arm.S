.syntax unified
.thumb
.section .vectors,"a",%progbits
.balign 128
.word stack_top
.word _start
.text
.thumb_func
.global _start
_start:
#ifdef ENABLE_FPU
  ldr r0, =0xe000ed88
  ldr r1, [r0]
  orr r1, r1, #(0xf << 20)
  str r1, [r0]
  dsb
  isb
#endif
  ldr r0, =boot_word
  movs r1, #91
  str r1, [r0]
#ifndef OMIT_ZERO
  movs r1, #0
  str r1, [r0]
#endif
  bl exercise
  movs r0, #'!'
  bl marker
  movs r0, #0x18
  ldr r1, =0x20026
  bkpt #0xab
  b .

.thumb_func
.global marker
marker:
  sub sp, #8
  str r0, [sp]
  mov r1, sp
  movs r0, #4
  bkpt #0xab
  add sp, #8
  bx lr
