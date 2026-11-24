ENTRY(_start)
PHDRS {
  text PT_LOAD FLAGS(5);
  data PT_LOAD FLAGS(6);
}
SECTIONS {
  . = 0x80000000;
  .text : { *(.text.boot) *(.text .text.*) } :text
  .data ALIGN(4096) : { *(.data) } :data
  .bss ALIGN(16) (NOLOAD) : { *(.bss) } :data
}
