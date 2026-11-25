ENTRY(_start)
SECTIONS
{
  . = 0x80000000;
  .text : { *(.text.start) *(.text .text.*) }
  . = ALIGN(4096);
  .bss (NOLOAD) : { *(.bss .bss.*) }
}
