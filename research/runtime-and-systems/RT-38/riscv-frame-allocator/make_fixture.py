def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError(f"Expected one base fixture hook for {before!r}")
    return source.replace(before, after)


def boot(source):
    source = replace_once(source, """  pte protected_leaves, 0, protected_word, 0x53  // Control: V/R/U/A.""",
                          """  la a0, protected_leaves
  call run_allocator""")
    source = replace_once(source, """user_probe:
  ld a0, 0(a2)
  li a7, 2
  ecall
  li a7, 3
  ecall""", """  li s0, 0
user_probe:
  ld a0, 0(a2)
  li a7, 2
  ecall
  addi s0, s0, 1
  li t0, 1
  beq s0, t0, probe_last_word
  li t0, 2
  beq s0, t0, probe_unmapped
  li a7, 3
  ecall
probe_last_word:
  li t0, 4088
  add a2, a2, t0
  j user_probe
probe_unmapped:
  addi a2, a2, 8
  j user_probe""")
    return ".set PROFILE, 3\n" + source


def layout(source):
    return replace_once(source, ".text : { *(.text.boot) *(.text.trap) }",
                        ".text : { *(.text.boot) *(.text.trap) *(.text .text.*) *(.rodata .rodata.*) }")
