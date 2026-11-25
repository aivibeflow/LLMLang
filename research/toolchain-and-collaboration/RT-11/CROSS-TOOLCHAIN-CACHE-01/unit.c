#include <stdint.h>

uint8_t increment(uint8_t input) {
#if SATURATE
    if (input == UINT8_MAX) {
        return UINT8_MAX;
    }
#endif
    return (uint8_t)(input + 1);
}
