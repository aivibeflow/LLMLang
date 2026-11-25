#include "abi.h"

#include <inttypes.h>
#include <stdio.h>

int main(void) {
    int32_t initial, quota, left, right;
    while (scanf("%" SCNd32 " %" SCNd32 " %" SCNd32 " %" SCNd32,
                 &initial, &quota, &left, &right) == 4) {
        struct runtime runtime = {.state = initial, .remaining = quota};
        const struct result result = emit_pair(&runtime, left, right);
        printf("%" PRId32 " %" PRId32 " %" PRId32 " %" PRId32 " %" PRId32,
               result.status, result.value, runtime.state, runtime.remaining, runtime.count);
        for (int32_t i = 0; i < runtime.count; ++i) {
            const struct observation event = runtime.events[i];
            printf(" %" PRId32 " %" PRId32 " %" PRId32,
                   event.tag, event.value, event.disposition);
        }
        putchar('\n');
    }
    return ferror(stdin) || ferror(stdout);
}
