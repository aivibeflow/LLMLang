#include <stdint.h>

#define UNCHANGED INT32_C(123456789)

enum disposition {
    accepted = 0,
    out_of_range = 1,
    policy_error = 2
};

int source_update(int32_t value, int32_t factor, int32_t offset, int32_t *output) {
    if (factor < -8 || factor > 8)
        return policy_error;
    const int64_t next = (int64_t)value * factor + offset;
    if (next < INT32_MIN || next > INT32_MAX) {
#ifdef MUTANT_EARLY_WRITE
        *output = 0;
#endif
        return out_of_range;
    }
    *output = (int32_t)next;
    return accepted;
}

struct observation {
    int32_t tag;
    int32_t output;
};

struct observation native_observation(int32_t value, int32_t factor, int32_t offset) {
    struct observation row = { .output = UNCHANGED };
    row.tag = source_update(value, factor, offset, &row.output);
    return row;
}
