.syntax unified
.cpu cortex-m3
.thumb

.equ SYSTICK, 0xE000E010
.equ SCB_ICSR, 0xE000ED04
.equ PENDSTCLR, 0x02000000
.equ PENDSTSET, 0x04000000
.equ PORT_F, 0x40025000

.section .text.timer,"ax",%progbits
.global timer_gpio_init, wait_tick, set_probe_pin, timer_interrupt, wrong_interrupt

.type timer_gpio_init,%function
.thumb_func
timer_gpio_init:
  ldr r0, =PORT_F
  movs r1, #3
  str r1, [r0, #0x400]  // GPIO direction
  str r1, [r0, #0x51c]  // Digital enable
  movs r1, #1
  str r1, [r0, #0x004]  // Bit 0 through its masked data address
  cpsie i
  bx lr

.type wait_tick,%function
.thumb_func
wait_tick:
  ldr r0, =SYSTICK
  movw r1, #1999
  str r1, [r0, #4]      // Reload interval
  movs r1, #0
  str r1, [r0, #8]      // Clear current count and COUNTFLAG
.ifdef POLLING
  movs r1, #5           // ENABLE and CLKSOURCE, TICKINT clear
  str r1, [r0]
1:
  ldr r1, [r0]
  tst r1, #0x10000
  beq 1b
  movs r1, #0
  str r1, [r0]
.else
  ldr r1, =SCB_ICSR
  mov.w r3, #PENDSTCLR
  str r3, [r1]
  dsb
  ldr r1, =irq_counter
  ldr r2, [r1]
  movs r3, #7           // ENABLE, TICKINT and CLKSOURCE
  str r3, [r0]
2:
  ldr r3, [r1]
  cmp r3, r2
  beq 2b
.endif
  bx lr

.type timer_interrupt,%function
.thumb_func
timer_interrupt:
  ldr r0, =SYSTICK
  movs r1, #0
  str r1, [r0]          // Disarm before publishing one interrupt observation
  ldr r0, =irq_counter
  ldr r1, [r0]
  ldr r2, =SCB_ICSR
.ifdef FORCE_PENDING
  cmp r1, #0
  bne 4f
  mov.w r3, #PENDSTSET
  str r3, [r2]
4:
.endif
.ifdef LEAVE_PENDING
  cmp r1, #0           // Withhold acknowledgement only for the injected event
  beq 5f
.endif
  mov.w r3, #PENDSTCLR
  str r3, [r2]
.ifdef LEAVE_PENDING
5:
.endif
  dsb
  isb
  adds r1, #1
  str r1, [r0]
  bx lr

.type set_probe_pin,%function
.thumb_func
set_probe_pin:
  cmp r0, #0
  ite ne
  movne r1, #2
  moveq r1, #0
  ldr r2, =PORT_F
.ifdef UNMASKED
  str r1, [r2, #0x3fc]
.else
  str r1, [r2, #0x008] // Only bit 1, preserving the neighboring output
.endif
  ldr r0, [r2, #0x3fc]
  and r0, r0, #3
  adds r1, #1
  cmp r0, r1
  bne gpio_fault
  bx lr

.type wrong_interrupt,%function
.thumb_func
wrong_interrupt:
  movs r0, #'V'
  bl uart_byte
  b fault
.type gpio_fault,%function
.thumb_func
gpio_fault:
  mov r4, r0
  movs r0, #'G'
  bl uart_byte
  mov r0, r4
  bl output_hex
fault:
  movs r0, #'X'
  bl uart_byte
3:
  wfi
  b 3b

.section .bss.irq_counter,"aw",%nobits
.balign 4
.global irq_counter
irq_counter:
.space 4
