.syntax unified
.cpu cortex-m3
.thumb

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
    ldr r0, =0x4000c000
    movs r1, #0x60
    str r1, [r0, #0x2c]
    movw r1, #0x0101
    str r1, [r0, #0x30]

    movs r0, #10
    movs r1, #11
    movs r2, #12
    bl set_words
    bl initialize
    bl report_words
    movs r0, #' '
    bl uart_byte

    movs r0, #5
    movs r1, #6
    movs r2, #7
    bl set_words
    bl initialize
    bl report_words
    movs r0, #'!'
    bl uart_byte

.type halt,%function
.thumb_func
halt:
    wfi
    b halt

.type set_words,%function
.thumb_func
set_words:
    ldr r3, =initialized
    str r0, [r3]
    ldr r3, =zeroed
    str r1, [r3]
    ldr r3, =retained
    str r2, [r3]
    bx lr

.type initialize,%function
.thumb_func
initialize:
#if PROFILE != 2
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
#endif
#if PROFILE != 3
    ldr r0, =__bss_start
#if PROFILE == 1
    ldr r1, =__retained_end
#else
    ldr r1, =__bss_end
#endif
    movs r2, #0
3:
    cmp r0, r1
    bhs 4f
    str r2, [r0], #4
    b 3b
4:
#endif
    bx lr

.type report_words,%function
.thumb_func
report_words:
    push {r4, lr}
    ldr r4, =initialized
    ldr r0, [r4]
    bl uart_nibble
    ldr r4, =zeroed
    ldr r0, [r4]
    bl uart_nibble
    ldr r4, =retained
    ldr r0, [r4]
    bl uart_nibble
    pop {r4, pc}

.type uart_nibble,%function
.thumb_func
uart_nibble:
    cmp r0, #10
    ite lo
    addlo r0, r0, #'0'
    addhs r0, r0, #('a' - 10)

.type uart_byte,%function
.thumb_func
uart_byte:
    ldr r1, =0x4000c000
5:
    ldr r2, [r1, #0x18]
    tst r2, #0x20
    bne 5b
    str r0, [r1]
    bx lr

.section .data,"aw",%progbits
.balign 4
initialized:
.word 2

.section .bss,"aw",%nobits
.balign 4
zeroed:
.space 4

.section .noinit,"aw",%nobits
.balign 4
retained:
.space 4
