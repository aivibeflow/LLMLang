"""Add machine timer delivery to the existing two-task RV64 context fixture."""


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f"Expected one occurrence of {before!r}")
    return source.replace(before, after)


def replace_region(source, start, end, replacement):
    left = source.index(start)
    right = source.index(end, left)
    return source[:left] + replacement + source[right:]


def render(source, schedule, mutation, a, b):
    source = replace_once(source, ".equ TEST_EXIT, 0x00100000\n", """.equ TEST_EXIT, 0x00100000
.equ MTIME, 0x0200bff8
.equ MTIMECMP, 0x02004000
.equ TIMER_CAUSE, ((1 << 63) | 7)
""")
    source = replace_once(
        source, "  j resume\n\n.balign 16",
        "  li t0, (1 << 7)\n  csrw mie, t0\n  j resume\n\n.balign 16",
    )
    source = replace_once(
        source,
        "  csrr t0, mcause\n  li t1, 8\n  bne t0, t1, fail\n",
        "  csrr s7, mcause\n",
    )
    source = replace_region(source, "trapped:\n", "stopping:\n", """trapped:
  li t0, TIMER_CAUSE
  beq s7, t0, timer
  li t0, 8
  bne s7, t0, fail
  li t0, 2
  beq a7, t0, stopping
  j report_user_fault

timer:
  ld t0, 0(sp)                    // Interrupted PC, never an ecall increment.
  la t1, user_entry
  bltu t0, t1, fail
  la t1, user_end
  bgeu t0, t1, fail
  andi t0, t0, 3
  bnez t0, fail
  ld t2, 0(s5)
  addi t2, t2, 1
  bgtu t2, a2, fail
  sd t2, 0(s5)
  sd t2, 128(sp)                  // Disclose delivered credits in saved a6.
.if MUTATION == 1
  sd zero, 64(sp)                 // Corrupt the user's saved s0.
.elseif MUTATION == 2
  la t0, lost_resume
  sd t0, 0(sp)                    // Refused continuation in the same user page.
.endif
  mv a0, s6
  call uart
.if POLICY == 1
  j resume
.else
  ld t0, 0(s4)
  bnez t0, resume
  mv sp, s2
  j resume
.endif

""")
    source = replace_once(source, "  bne t0, a2, fail\n  li t0, 1\n",
                          "  bne t0, a2, fail\n  bne a6, a2, fail\n  li t0, 1\n")
    source = replace_once(source, "resume:\n  restore t0, 0\n", """resume:
  li t0, MTIMECMP
  restore t1, 16
  restore t2, 12
  bgeu t1, t2, park_timer
  li t1, MTIME
  ld t1, 0(t1)
  addi t1, t1, 128
  j set_timer
park_timer:
  li t1, -1
set_timer:
  sd t1, 0(t0)
  restore t0, 0
""")
    source = replace_region(source, "worker:\n", "user_stop:\n", """worker:
  addi s1, s1, 1
  addi t0, a1, 100
  bne s0, t0, bad_saved
  ld t1, 0(sp)
  bne t1, t0, bad_stack
  addi t0, a1, 200
  bne t3, t0, bad_t3
  bltu a6, a2, worker
  li a7, 2
""")
    source = replace_once(source, "bad_t3:\n  li a7, 243\nfault_ecall:\n", """bad_t3:
lost_resume:
  li a7, 243
fault_ecall:
""")
    source = replace_once(source, '.section .bss.kernel,"aw",@nobits',
                          'user_end:\n\n.section .bss.kernel,"aw",@nobits')
    source = replace_once(source, ".global user_entry, user_yield, user_stop",
                          ".global user_entry, user_stop")
    return f".set POLICY, {schedule}\n.set MUTATION, {mutation}\n.set WORK_A, {a}\n.set WORK_B, {b}\n" + source
