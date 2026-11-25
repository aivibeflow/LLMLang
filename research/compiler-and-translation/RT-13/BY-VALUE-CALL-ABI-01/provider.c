#include "provider.h"

__attribute__((noinline))
struct Pair CALL_ABI transform_record(struct Pair input, uint64_t salt) {
    return (struct Pair){
        .x = input.x + (input.y ^ salt),
        .y = input.y + UINT64_C(3) * salt + UINT64_C(5) * input.x,
    };
}

void bridge_record(const struct Pair *input, uint64_t salt, struct Pair *output) {
    *output = transform_record(*input, salt);
}

unsigned provider_call_style(void) {
    return CALL_STYLE;
}
