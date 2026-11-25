.syntax unified
.cpu cortex-m3
.thumb

.equ NVIC_SET_PENDING, 0xe000e200
.equ NVIC_CLEAR_PENDING, 0xe000e280

.section .vectors,"a",%progbits
.word __stack_top
.word reset
.rept 14
.word halt
.endr

.section .text,"ax",%progbits
.global reset
.type reset,%function
.thumb_func
reset:
    cpsid i
    ldr r0, =0x4000c000
    movs r1, #0x60
    str r1, [r0, #0x2c]
    movw r1, #0x0101
    str r1, [r0, #0x30]

    movs r0, #1
    bl report_case
    movs r0, #' '
    bl uart
    movs r0, #2
    bl report_case
    movs r0, #'!'
    bl uart
.thumb_func
halt:
    wfi
    b halt

.thumb_func
report_case:
    push {r3, r4, r5, r6, r7, lr}
    mov r7, r0
    ldr r1, =NVIC_CLEAR_PENDING
    ldr r2, =NVIC_SET_PENDING
    movs r0, #3
    str r0, [r1]  // Start with both selected lanes clear.
    str r0, [r2]  // Pend both selected lanes.
    dsb
    ldr r4, [r2]  // Observe pending state through the set alias.
    ldr r5, [r1]  // Observe the same state through the clear alias.
#if PROFILE == 0
    str r7, [r1]
#elif PROFILE == 1
    orr r0, r5, r7
    str r0, [r1]
#elif PROFILE == 2
    bic r0, r5, r7
    str r0, [r1]
#elif PROFILE == 3
    str r7, [r2]
#else
#error unsupported profile
#endif
    dsb
    ldr r6, [r2]
    and r0, r4, #3
    adds r0, #'0'
    bl uart
    and r0, r5, #3
    adds r0, #'0'
    bl uart
    and r0, r6, #3
    adds r0, #'0'
    bl uart
    pop {r3, r4, r5, r6, r7, pc}

.thumb_func
uart:
    ldr r1, =0x4000c000
1:
    ldr r2, [r1, #0x18]
    tst r2, #0x20
    bne 1b
    str r0, [r1]
    bx lr
