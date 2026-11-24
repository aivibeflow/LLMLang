def replace_once(source, previous, replacement):
    if source.count(previous) != 1:
        raise ValueError(f"Expected one source hook for {previous!r}")
    return source.replace(previous, replacement)


def render(source, policy):
    dispatch = "  li t0, 99\n  bne a7, t0, fail\n"
    source = replace_once(source, dispatch, "  li t0, 5\n  beq a7, t0, remap\n"
                          "  li t0, 6\n  beq a7, t0, revoke\n" + dispatch)
    old = """report_value:
  ld t0, 40(sp)
  li t1, PRIVATE_VALUE
  beq t0, t1, visible
  bnez t0, fail
  li a0, 'Z'
  j report_byte
visible:
  li a0, 'V'
"""
    new = """report_value:
  ld t0, 40(sp)
  li t1, PRIVATE_VALUE
  beq t0, t1, frame_a_visible
  li t1, 0x56789def
  beq t0, t1, frame_b_visible
  bnez t0, fail
  li a0, 'Z'
  j report_byte
frame_a_visible:
  li a0, 'A'
  j report_byte
frame_b_visible:
  li a0, 'B'
"""
    source = replace_once(source, old, new)
    update = """remap:
  pte protected_leaves, 0, replacement_frame, 0x53
  ld t2, 0(t0)
  bne t2, t1, fail
  call synchronize_translation
  li a0, 'M'
  j report_byte
revoke:
  la t0, protected_leaves
  sd zero, 0(t0)
  ld t2, 0(t0)
  bnez t2, fail
  call synchronize_translation
  li a0, 'D'
  j report_byte

.global synchronize_translation
.type synchronize_translation,@function
synchronize_translation:
  fence rw, rw
.if FENCE_POLICY == 0
  sfence.vma zero, zero
.elseif FENCE_POLICY == 1
  li t0, PROTECTED_VA
  sfence.vma t0, zero
.elseif FENCE_POLICY == 2
  li t0, PROTECTED_VA + 4096
  sfence.vma t0, zero
.endif
  ret
.size synchronize_translation, .-synchronize_translation

"""
    source = replace_once(source, "finish:\n  li a0, '!'\n", update + "finish:\n  li a0, '!'\n")
    old = """user_probe:
  ld a0, 0(a2)
  li a7, 2
  ecall
  li a7, 3
  ecall
"""
    loop = """  li s0, 0
user_probe:
  ld a0, 0(a2)
  li a7, 2
  ecall
  beqz s0, request_remap
  li t0, 1
  beq s0, t0, request_revoke
  li a7, 3
  ecall
request_remap:
  li a7, 5
  ecall
  li s0, 1
  j user_probe
request_revoke:
  li a7, 6
  ecall
  li s0, 2
  j user_probe
"""
    source = replace_once(source, old, loop)
    source = replace_once(source, "protected_word:\n.quad PRIVATE_VALUE\n", """protected_word:
.quad PRIVATE_VALUE
.balign 4096
.global replacement_frame
replacement_frame:
.quad 0x56789def
""")
    return f".set PROFILE, 3\n.set FENCE_POLICY, {policy}\n" + source
