#ifndef RT13_LINUX_TRIPLE_ABI_H
#define RT13_LINUX_TRIPLE_ABI_H

#include <stdint.h>

struct ledger {
    uint64_t generation;
    uint32_t state;
    uint32_t status;
};

typedef void (*observe)(void *, uint32_t, uint32_t);

struct ledger transition(struct ledger current, uint32_t delta, observe sink, void *context);

#endif
