#ifndef RUNTIME_ABI_H
#define RUNTIME_ABI_H

#include <stdint.h>

enum { ACCEPTED = 0, QUOTA_EXHAUSTED = 1, NO_RESULT = -99 };

struct observation {
    int32_t tag;
    int32_t value;
    int32_t disposition;
};

struct runtime {
    int32_t state;
    int32_t remaining;
    int32_t count;
    struct observation events[2];
};

struct result {
    int32_t status;
    int32_t value;
};

int32_t rt_emit(struct runtime *runtime, int32_t tag, int32_t value);
struct result emit_pair(struct runtime *runtime, int32_t left, int32_t right);

#endif
