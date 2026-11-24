from request_vectors import A, B


def only(source, previous, replacement):
    if source.count(previous) != 1:
        raise ValueError(f"Unexpected scheduler source near {previous!r}")
    return source.replace(previous, replacement)


def boot(source):
    first = source.index("  li t0, 1\n  bne a7, t0, report_user_fault")
    last = source.index("\nstopping:", first)
    source = source[:first] + """  li t0, 3
  bne a7, t0, fail
  la t0, user_ipc
  ld t1, 0(sp)
  bne t0, t1, fail
  addi t1, t1, 4
  sd t1, 0(sp)
  ld t0, 0(s5)
  addi t0, t0, 1
  bgtu t0, a2, fail
  sd t0, 0(s5)
  mv a0, a1
  mv a1, a3
  mv a2, a4
  mv a3, a5
  mv s0, sp
  la sp, ipc_stack_top
  call ipc_request
  mv sp, s0
  sd a0, 80(sp)                  // Return the result to the caller's a0.
  ld t0, 0(s4)
  bnez t0, resume
  mv sp, s2
  j resume
""" + source[last:]
    source = source[:source.index(".section .user.text")] + """.section .user.text,"ax",@progbits
.global user_entry, user_ipc, user_stop
user_entry:
  la s2, script_a
  beqz a1, request
  la s2, script_b
request:
  lbu a3, 0(s2)
  beqz a3, done
  lbu a4, 1(s2)
  lbu a5, 2(s2)
  li a7, 3
user_ipc:
  ecall
  addi s2, s2, 3
  j request
done:
  li a7, 2
user_stop:
  ecall
  j .

"""
    for actor, requests in (("a", A), ("b", B)):
        source += f"script_{actor}:\n"
        source += "".join(f"  .byte {operation}, {handle}, {value}\n" for operation, handle, value in requests)
        source += "  .byte 0\n"
    return source


def assembly(source):
    state_start = source.index('.section .bss.kernel')
    body = boot(source)
    # The old diagnostics refer to a cooperative worker's fault ecall.
    start, end = body.index("report_user_fault:"), body.index("fail:\n")
    body = body[:start] + body[end:]
    return f".set POLICY, 0\n.set WORK_A, {len(A)}\n.set WORK_B, {len(B)}\n" + body + source[state_start:] + """
.section .bss.kernel,"aw",@nobits
.balign 16
.space 4096
ipc_stack_top:
"""


def linker(source):
    source = only(source, ".bss ALIGN(4096) (NOLOAD) : { *(.bss.kernel) } :state",
                  ".data ALIGN(4096) : { *(.data.kernel) } :state\n"
                  "  .bss ALIGN(256) (NOLOAD) : { *(.bss.kernel) } :state")
    return only(source, ".text : { *(.text.boot) }", ".text : { *(.text.boot) *(.text .text.*) }")
