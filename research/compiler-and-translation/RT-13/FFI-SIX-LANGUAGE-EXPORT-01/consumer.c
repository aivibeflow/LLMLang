#include "public.h"
#include <inttypes.h>
#include <stdio.h>

int main(void) {
    uint64_t input;
    uint32_t enabled;
    while (scanf("%" SCNu64 " %" SCNu32, &input, &enabled) == 2) {
        uint64_t slot = UINT64_C(0xabad1234abcdef01);
        uint32_t code = checked_add(input, enabled, &slot);
        printf("%" PRIu32 " %" PRIu64 "\n", code, slot);
    }
}
