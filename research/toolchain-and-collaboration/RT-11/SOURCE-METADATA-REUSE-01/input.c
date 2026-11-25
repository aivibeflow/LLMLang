/* Source-location profile fixture. */
#include <stdint.h>

uint32_t step(uint32_t input)
{
#if USE_LINE
    return input + (uint32_t)__LINE__;
#else
    return input + UINT32_C(1);
#endif
}
