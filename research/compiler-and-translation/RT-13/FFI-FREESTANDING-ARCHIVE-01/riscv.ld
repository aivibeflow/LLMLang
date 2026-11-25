ENTRY(_start)
PHDRS {
  code PT_LOAD FLAGS(5);
  state PT_LOAD FLAGS(6);
}
SECTIONS {
  . = 0x80000000;
  .text : { *(.text .text.*) *(.rodata .rodata.*) } :code
  . = ALIGN(4096);
  .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.* COMMON) . = ALIGN(16); . += 4096; stack_top = .; } :state
  /DISCARD/ : { *(.comment) }
}
