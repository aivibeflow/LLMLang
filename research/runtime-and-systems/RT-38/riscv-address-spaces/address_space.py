def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Unexpected base assembly hook for {old!r}")
    return source.replace(old, new)


def assembly(source, profile):
    source = once(source, ".equ TEST_EXIT, 0x00100000\n", r""".equ TEST_EXIT, 0x00100000
.equ USER_CODE_VA, 0x40000000
.equ USER_STACK_TOP, 0x40002000
.equ USER_IMAGE_DELTA, 0x40200000

.macro map_page table, offset, frame, flags
  la t0, \table
  la t1, \frame
  srli t1, t1, 12
  slli t1, t1, 10
  ori t1, t1, \flags
  sd t1, \offset(t0)
.endm

.macro user_symbol_in_t0 symbol
  la t0, \symbol
  li t1, USER_IMAGE_DELTA
  sub t0, t0, t1
.endm
""")
    start = source.index("  la t0, user_entry\n")
    end = source.index("  csrr t0, mstatus\n", start)
    source = source[:start] + """  li t0, -1
  csrw pmpaddr0, t0
  li t0, 0xf
  csrw pmpcfg0, t0
  csrr t1, pmpcfg0
  bne t0, t1, fail
  la t0, root_a
  la t1, tables_end
zero_tables:
  sd zero, 0(t0)
  addi t0, t0, 8
  bne t0, t1, zero_tables
  map_page root_a, 8, directory_a, 1
  map_page root_b, 8, directory_b, 1
  map_page directory_a, 0, leaves_a, 1
  map_page directory_b, 0, leaves_b, 1
  map_page leaves_a, 0, user_entry, 0x5b
  map_page leaves_b, 0, user_entry, 0x5b
  map_page leaves_a, 8, stack_a, 0xd7
.if SPACE_PROFILE == 2
  map_page leaves_b, 8, stack_a, 0xd7
.else
  map_page leaves_b, 8, stack_b, 0xd7
.endif
.if SPACE_PROFILE == 3
  map_page leaves_a, 16, stack_b, 0x53
.endif
  la t0, stack_a
  li t1, 0x1122
  sd t1, 0(t0)
  la t0, stack_b
  li t1, 0x3344
  sd t1, 0(t0)
  fence rw, rw
  sfence.vma zero, zero         // Order the newly initialized leaves before first use.
""" + source[end:]
    source = once(source, "  la sp, context_a\n  la t0, user_entry\n", "  la sp, context_a\n  li t0, USER_CODE_VA\n")
    source = once(source, "  la t0, stack_a_top\n", "  li t0, USER_STACK_TOP\n")
    source = once(source, "  la t1, user_entry\n", "  li t1, USER_CODE_VA\n")
    source = once(source, "  la t1, stack_b_top\n", "  li t1, USER_STACK_TOP\n")
    source = once(source, """  csrr t0, mcause
  li t1, 8
  bne t0, t1, fail

  la t0, context_a""", """  la t0, context_a""")
    source = once(source, """trapped:
  li t0, 2
""", """trapped:
  csrr t0, mcause
  li t1, 13
  beq t0, t1, blocked_read
  li t1, 8
  bne t0, t1, fail
  li t0, 5
  beq a7, t0, reported_read
  li t0, 6
  beq a7, t0, reported_stack
  li t0, 2
""")
    source = once(source, "  la t0, user_ipc\n", "  user_symbol_in_t0 user_ipc\n")
    source = once(source, "  la t0, user_stop\n", "  user_symbol_in_t0 user_stop\n")
    source = once(source, "resume:\n  restore t0, 0\n", """blocked_read:
  user_symbol_in_t0 user_read_peer
  ld t1, 0(sp)
  bne t0, t1, fail
  csrr t2, mtval
  li t0, USER_STACK_TOP
  bne t2, t0, fail
  addi t1, t1, 4
  sd t1, 0(sp)
  sd zero, 104(sp)
  addi a0, s6, 47
  call uart
  j resume
reported_read:
  user_symbol_in_t0 user_read_report
  ld t1, 0(sp)
  bne t0, t1, fail
  li t0, 0x3344
  bne a3, t0, fail
  li a0, 'V'
  call uart
  j poweroff
reported_stack:
  user_symbol_in_t0 user_stack_report
  ld t1, 0(sp)
  bne t0, t1, fail
  li a0, 'K'
  call uart
  j poweroff
resume:
  la t0, context_a
  beq sp, t0, select_a
  la t0, root_b
.if SPACE_PROFILE == 1
  li t2, ((8 << 60) | (1 << 44))
.else
  li t2, (8 << 60)
.endif
  j install_translation
select_a:
  la t0, root_a
  li t2, (8 << 60)
.global install_translation
.type install_translation,@function
install_translation:
  srli t0, t0, 12
  or t0, t0, t2
  fence rw, rw
  csrw satp, t0
.if SPACE_PROFILE != 1 && SPACE_PROFILE != 4
  sfence.vma zero, zero
.endif
  csrr t1, satp
  bne t0, t1, fail
.size install_translation, .-install_translation
  restore t0, 0
""")
    source = once(source, """user_entry:
  la s2, script_a
""", """user_entry:
  addi sp, sp, -16
  addi s0, a1, 100
  sd s0, 0(sp)
  li a6, USER_STACK_TOP
user_read_peer:
  ld a3, 0(a6)
  beqz a3, private_probe_done
  li a7, 5
user_read_report:
  ecall
  j .
private_probe_done:
  la s2, script_a
""")
    source = once(source, """user_ipc:
  ecall
  addi s2, s2, 3
""", """user_ipc:
  ecall
  ld t0, 0(sp)
  bne t0, s0, bad_stack
  addi s2, s2, 3
""")
    source = once(source, "script_a:\n", """bad_stack:
  li a7, 6
user_stack_report:
  ecall
  j .
script_a:
""")
    return f".set SPACE_PROFILE, {profile}\n" + source + """
.section .bss.kernel,"aw",@nobits
.balign 4096
root_a: .space 4096
directory_a: .space 4096
leaves_a: .space 4096
root_b: .space 4096
directory_b: .space 4096
leaves_b: .space 4096
tables_end:
"""


def linker(source):
    return once(source, ".bss ALIGN(256) (NOLOAD)", ".bss ALIGN(4096) (NOLOAD)")
