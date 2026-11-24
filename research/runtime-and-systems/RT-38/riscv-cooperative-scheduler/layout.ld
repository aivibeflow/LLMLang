ENTRY(_start)
PHDRS {
  kernel PT_LOAD FLAGS(5);
  state  PT_LOAD FLAGS(6);
  user   PT_LOAD FLAGS(5);
  stack  PT_LOAD FLAGS(6);
}

SECTIONS {
  . = 0x80000000;
  .text : { *(.text.boot) } :kernel
  .bss ALIGN(4096) (NOLOAD) : { *(.bss.kernel) } :state
  . = 0x80200000;
  .user : { *(.user.text) } :user
  . = 0x80201000;
  .user_stack (NOLOAD) : { *(.user.stack) } :stack
}
