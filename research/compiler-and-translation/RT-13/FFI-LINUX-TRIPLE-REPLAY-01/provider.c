#include "abi.h"

struct ledger transition(struct ledger current, uint32_t delta, observe sink, void *context) {
    sink(context, 11, delta);
    if (delta > 32 || current.state > 100 || delta > 100 - current.state) {
        current.status = 1;
        sink(context, 29, current.state);
        return current;
    }
    current.generation += 1;
    current.state += delta;
    current.status = 0;
#ifndef OMIT_COMMIT_EVENT
    sink(context, 23, current.state);
#endif
    return current;
}
