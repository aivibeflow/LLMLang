"""Compose a two-root Sv39 fixture with timer delivery and a generation-checked wait."""

from pathlib import Path


HERE = Path(__file__).resolve().parent


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f"Expected one occurrence of {before!r}")
    return source.replace(before, after)


def splice(source, start, end, replacement):
    left = source.index(start)
    right = source.index(end, left)
    return source[:left] + replacement + source[right:]


def render(timer, mode, mutant):
    start = splice(timer, "  la t0, user_entry\n", "  csrr t0, mstatus\n",
                   (HERE / "mapping.s.in").read_text(encoding="utf-8"))
    start = replace_once(start, "la t1, stack_b_top", "la t1, stack_a_top")
    start = replace_once(start, "  li t0, (1 << 7)\n", """  la t0, endpoint_generation
  li t1, 1
  sd t1, 0(t0)
  li t1, MODE
  sd t1, 112(sp)
  la t0, context_b
  sd t1, 112(t0)
  li t0, (1 << 7)
""")
    start = splice(start, "trapped:\n", "stopping:\n",
                   (HERE / "dispatch.s.in").read_text(encoding="utf-8"))
    start = replace_once(start, "\nresume:\n", """
resume:
  la t0, context_a
  beq sp, t0, root_for_a
  la t0, root_b
  j install_root
root_for_a:
  la t0, root_a
install_root:
  srli t0, t0, 12
  li t1, (8 << 60)
  or t0, t0, t1
  csrw satp, t0
  sfence.vma zero, zero
  csrr t1, satp
  bne t0, t1, fail
""")
    start = splice(start, "user_entry:\n", "user_end:\n",
                   (HERE / "tasks.s.in").read_text(encoding="utf-8"))
    start = replace_once(start, "  la t0, fault_ecall\n", "  la t0, user_fault\n")
    start = replace_once(start, "completed_b: .space 8\n", """completed_b: .space 8
waiting: .space 8
endpoint_generation: .space 8
.balign 4096
root_a: .space 4096
directory_a: .space 4096
leaves_a: .space 4096
root_b: .space 4096
directory_b: .space 4096
leaves_b: .space 4096
tables_end:
""")
    return f".set MODE, {mode}\n.set MUTANT, {mutant}\n" + start
