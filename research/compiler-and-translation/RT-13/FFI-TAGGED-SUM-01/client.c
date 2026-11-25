#include "abi.h"

#include <inttypes.h>
#include <math.h>
#include <stdio.h>

static void print(Result out) {
    printf("%u:%u:%" PRId64 "\n", out.disposition, out.reserved, out.value);
}

int main(void) {
    int capability;
    const Sum supplied[] = {
        {0, 0, {.integer = -7}}, {0, 0, {.integer = INT64_MAX}}, {0, 1, {.integer = 99}},
        {1, 0, {.floating = -3.25}}, {1, 0, {.floating = 128.0}}, {1, 0, {.floating = 129.0}},
        {1, 0, {.floating = NAN}}, {2, 0, {.pointer = &capability}}, {2, 0, {.pointer = NULL}},
        {99, 0, {.integer = 11}},
    };
    for (unsigned index = 0; index < sizeof(supplied) / sizeof(supplied[0]); ++index) {
        print(call_sysv(supplied[index], &capability));
        print(call_ms(supplied[index], &capability));
    }
#ifdef WRONG_CALL_CONVENTION
    Result (__attribute__((sysv_abi)) *wrong)(Sum, const void *) = call_ms;
    (void)wrong;
#endif
}
