ENTRY(reset)
MEMORY {
  FLASH (rx) : ORIGIN = 0x00000000, LENGTH = 256K
  RAM (rw) : ORIGIN = 0x20000000, LENGTH = 64K
}
__stack_top = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS {
  .vectors : { KEEP(*(.vectors)) } > FLASH
  .text : { *(.text*) } > FLASH
  .data : {
    __data_start = .;
    *(.data)
    __data_end = .;
  } > RAM AT > FLASH
  __data_load = LOADADDR(.data);
  .bss (NOLOAD) : {
    __bss_start = .;
    *(.bss)
    __bss_end = .;
  } > RAM
  .noinit (NOLOAD) : {
    __retained_start = .;
    *(.noinit)
    __retained_end = .;
  } > RAM
}
ASSERT(__data_end <= __bss_start, "data overlaps bss")
ASSERT(__bss_end <= __retained_start, "bss overlaps retained RAM")
ASSERT(__retained_end + 64 <= __stack_top, "insufficient reserved stack space")
