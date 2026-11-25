#include <stdint.h>

int32_t quotient(uint64_t high, uint64_t low, uint64_t divisor, uint64_t *slot) {
    if (divisor == 0) {
        return 1;
    }
#if WIDE
    unsigned __int128 dividend = ((unsigned __int128)high << 64) | low;
    unsigned __int128 value = dividend / divisor;
    if (value > UINT64_MAX) {
        return 2;
    }
    *slot = (uint64_t)value;
#else
#if !SILENT_NARROW
    if (high != 0) {
        return 3;
    }
#else
    (void)high;
#endif
    *slot = low / divisor;
#endif
    return 0;
}
