#include "abi.h"

#include <assert.h>

int32_t rt_emit(struct runtime *runtime, int32_t tag, int32_t value) {
    assert(runtime->count < 2);
    const int32_t outcome = runtime->remaining > 0 ? ACCEPTED : QUOTA_EXHAUSTED;
#ifdef MUTATE_RUNTIME_EVENT
    tag ^= 64;
#endif
    runtime->events[runtime->count++] = (struct observation){tag, value, outcome};
    if (outcome == ACCEPTED) {
        --runtime->remaining;
        runtime->state += value;
    }
    return outcome;
}
