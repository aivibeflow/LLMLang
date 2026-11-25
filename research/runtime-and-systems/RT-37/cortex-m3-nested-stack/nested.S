.syntax unified
.cpu cortex-m3
.thumb

.section .vectors,"a",%progbits
.word __stack_top
.word reset
.rept 12
.word halt
.endr
.word pending_low
.word pending_tick

.macro record letter
    ldr r0, =trace_length
    ldr r1, [r0]
    ldr r2, =trace
    movs r3, #\letter
    strb r3, [r2, r1]
    adds r1, #1
    str r1, [r0]
.endm

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
    ldr r0, =trace_length
    movs r1, #0
    str r1, [r0]
    mrs r1, msp
    ldr r0, =thread_sp
    str r1, [r0]

    ldr r0, =0xe000ed20  // SHPR3, PendSV and SysTick priorities.
#if PROFILE == 1
    ldr r1, =0x80800000
#else
    ldr r1, =0x40800000
#endif
    str r1, [r0]
    ldr r0, =0xe000e010  // SysTick TICKINT with its counter disabled.
    movs r1, #2
    str r1, [r0]
    dsb
    isb
    ldr r0, =0xe000ed04
    ldr r1, =0x10000000  // PENDSVSET.
    str r1, [r0]
    dsb
    isb
1:
    ldr r0, =trace_length
    ldr r0, [r0]
    cmp r0, #2
    blo 1b
#if PROFILE == 3
    cpsie i
    isb
#endif
2:
    ldr r0, =trace_length
    ldr r0, [r0]
    cmp r0, #3
    blo 2b

    ldr r4, =trace
    ldrb r0, [r4]
    bl uart_byte
    ldrb r0, [r4, #1]
    bl uart_byte
    ldrb r0, [r4, #2]
    bl uart_byte

    ldr r4, =thread_sp
    ldr r4, [r4]
    movs r0, #' '
    bl uart_byte
    ldr r0, =low_sp
    ldr r0, [r0]
    subs r0, r4, r0
    bl uart_hex
    movs r0, #' '
    bl uart_byte
    ldr r0, =tick_sp
    ldr r0, [r0]
    subs r0, r4, r0
    bl uart_hex
    movs r0, #'!'
    bl uart_byte

.thumb_func
halt:
    wfi
    b halt

.thumb_func
pending_low:
    mrs r1, msp
    ldr r0, =low_sp
    str r1, [r0]
    record 76   // L.
#if PROFILE == 2 || PROFILE == 3
    cpsid i
#endif
    ldr r0, =0xe000ed04
    ldr r1, =0x04000000  // PENDSTSET.
    str r1, [r0]
    dsb
    isb
    record 108  // l.
#if PROFILE == 2
    cpsie i
    isb
#endif
    bx lr

.thumb_func
pending_tick:
    mrs r1, msp
    ldr r0, =tick_sp
    str r1, [r0]
    record 72   // H.
    bx lr

.thumb_func
uart_hex:
    push {r4, lr}
    mov r4, r0
    lsrs r0, r0, #4
    bl uart_nibble
    and r0, r4, #15
    bl uart_nibble
    pop {r4, pc}

.thumb_func
uart_nibble:
    cmp r0, #10
    ite lo
    addlo r0, r0, #'0'
    addhs r0, r0, #('a' - 10)

.thumb_func
uart_byte:
    ldr r1, =0x4000c000
3:
    ldr r2, [r1, #0x18]
    tst r2, #0x20
    bne 3b
    str r0, [r1]
    bx lr

.section .bss,"aw",%nobits
.balign 4
trace_length: .space 4
trace: .space 4
thread_sp: .space 4
low_sp: .space 4
tick_sp: .space 4
