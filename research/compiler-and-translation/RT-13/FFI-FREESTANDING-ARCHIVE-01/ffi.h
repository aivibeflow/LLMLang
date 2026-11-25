#ifndef RT13_FREESTANDING_ABI_H
#define RT13_FREESTANDING_ABI_H

typedef unsigned int u32;
_Static_assert(sizeof(u32) == 4, "fixed ABI width");

struct outcome {
    u32 value;
    u32 status;
};

typedef void (*event_sink)(void *, u32);

u32 checked_support(u32);
struct outcome dispatch(u32 state, u32 request, event_sink sink, void *context);
void marker(u32 code);
void exercise(void);

#endif
