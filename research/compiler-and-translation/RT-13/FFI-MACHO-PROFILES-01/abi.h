#ifndef RT13_MACHO_ABI_H
#define RT13_MACHO_ABI_H

typedef unsigned int u32;
typedef unsigned long u64;

struct span {
    u64 origin;
    u32 length;
    u32 status;
};

_Static_assert(sizeof(void *) == 8 && sizeof(long) == 8, "Apple LP64");
_Static_assert(sizeof(struct span) == 16 && _Alignof(struct span) == 8, "ABI layout");
_Static_assert(__builtin_offsetof(struct span, status) == 12, "ABI field offset");

struct span update_span(struct span from, u32 requested);
u32 observe_span(void);
#endif
