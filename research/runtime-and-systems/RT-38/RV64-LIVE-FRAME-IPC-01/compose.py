"""Add replacement-frame allocation to the integrated timer and IPC guest."""

from pathlib import Path


HERE = Path(__file__).resolve().parent


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f"Expected one occurrence of {before!r}")
    return source.replace(before, after)


def render(guest, control):
    source = once(guest, "  map leaves_a, 8, stack_a, 0xd7\n", """  map leaves_a, 8, stack_a, 0xd7
  map leaves_a, 24, old_frame, 0xd7
  la t0, old_frame
  li t1, 0x11
  sd t1, 0(t0)
  la t0, replacement_frame
  li t1, 0x33
  sd t1, 0(t0)
  addi t0, t0, 2047
  addi t0, t0, 2041
  sd t1, 0(t0)
""")
    source = once(source, "  beq s7, t0, timer\n", """  beq s7, t0, timer
  li t0, 13
  beq s7, t0, private_page_fault
""")
    source = once(source, "  bne t1, a0, fail\n  sd zero, 0(t0)\n",
                  "  bne t1, a0, fail\n")
    source = once(source, "  sd t1, 0(t2)\n  li t1, 17\n", """  sd t1, 0(t2)
  call replace_lease
  la t0, waiting
  sd zero, 0(t0)
  li t1, 17
""")
    source = once(source, "\nstopping:\n",
                  "\n" + (HERE / "replace.s.in").read_text(encoding="utf-8") + "\nstopping:\n")
    source = once(source, "  bnez a1, sender_wait\n", """  bnez a1, sender_probe
  li t1, 0x80203000
  ld t0, 0(t1)
  li t1, 0x11
  bne t0, t1, bad_result
""")
    source = once(source, "  bne a0, t0, bad_result\nreceiver_wait:\n", """  bne a0, t0, bad_result
  li t1, 0x80203000
  li t2, 0x80204000
scan_frame:
  ld t0, 0(t1)
  li t4, 0x11
  beq t0, t4, old_replayed
  bnez t0, dirty_frame
  addi t1, t1, 8
  bne t1, t2, scan_frame
receiver_wait:
""")
    source = once(source, "\nsender_wait:\n", """
sender_probe:
  li t0, 0x80203000
sender_private_probe:
  ld a5, 0(t0)
  bnez a5, bad_result
sender_wait:
""")
    source = once(source, "bad_result:\n", """dirty_frame:
  li a7, 244
  j user_fault
old_replayed:
  li a7, 245
  j user_fault
bad_result:
""")
    source = once(source, "  li t0, 243\n  bne a7, t0, fail\n", """  li t0, 244
  beq a7, t0, dirty_report
  li t0, 245
  beq a7, t0, old_report
  li t0, 243
  bne a7, t0, fail
""")
    source = once(source, "saved_register_fault:\n",
                  """dirty_report:
  li a0, 'M'
  j report_fault
old_report:
  li a0, 'O'
  j report_fault
saved_register_fault:
""")
    source += """
.section .bss.kernel,"aw",@nobits
.balign 4096
old_frame: .space 4096
replacement_frame: .space 4096
replacement_live: .space 8
"""
    return f".set LEASE_CONTROL, {control}\n" + source
