#include <stdint.h>

#ifndef PROFILE
#error PROFILE is required
#endif
#ifndef OFFSET
#error OFFSET is required
#endif
#ifndef RELEASE
#error RELEASE is required
#endif

const char *rt_release(void) {
    return RELEASE;
}

uint32_t rt_sample(uint32_t input) {
    uint32_t tag = input % 3u;
    uint32_t contents = tag == 0u ? input + OFFSET : (tag == 1u ? 11u : 17u);
#if PROFILE == 1
    return (tag << 24) | contents;
#elif PROFILE == 2
    return (contents << 16) | tag;
#else
#error Unknown PROFILE
#endif
}
