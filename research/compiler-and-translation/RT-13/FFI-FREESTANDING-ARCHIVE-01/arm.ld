ENTRY(_start)
PHDRS {
  flash PT_LOAD FLAGS(5);
  state PT_LOAD FLAGS(6);
}
SECTIONS {
  . = 0;
  .vectors : { KEEP(*(.vectors)) } :flash
  .text : { *(.text .text.*) *(.rodata .rodata.*) } :flash
  . = 0x20000000;
  .bss (NOLOAD) : { *(.bss .bss.* COMMON) } :state
  stack_top = 0x20004000;
  /DISCARD/ : { *(.ARM.exidx*) *(.comment) }
}
