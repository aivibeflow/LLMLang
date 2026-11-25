#include "provider.h"
#include <inttypes.h>
#include <stdio.h>

int main(void) {
    const uint64_t values_x[] = {0, 1, UINT64_C(4294967297), UINT64_MAX};
    const uint64_t values_y[] = {0, 2, UINT64_C(1099511627779), UINT64_MAX};
    const uint64_t salts[] = {0, 3, UINT64_C(9223372036854775807), UINT64_MAX};

    printf("[%zu,%zu,%zu,%zu,%u]\n", sizeof(struct Pair), _Alignof(struct Pair),
           offsetof(struct Pair, x), offsetof(struct Pair, y), provider_call_style());
    for (size_t x = 0; x < 4; ++x)
        for (size_t y = 0; y < 4; ++y)
            for (size_t salt = 0; salt < 4; ++salt) {
                const struct Pair input = {values_x[x], values_y[y]};
                struct Pair output;
#if USE_BRIDGE
                bridge_record(&input, salts[salt], &output);
#else
                output = transform_record(input, salts[salt]);
#endif
                printf("[%" PRIu64 ",%" PRIu64 "]\n", output.x, output.y);
            }
    return 0;
}
