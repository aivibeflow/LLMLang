#include <stdint.h>

int32_t divide(uint64_t numerator, uint64_t divisor, uint32_t enabled,
               uint32_t receipt, uint64_t *slot, uint32_t *route) {
    if (divisor == 0) {
        *route = 0;
        return 1;
    }

    if (enabled && receipt == 1) {
        unsigned shift = (unsigned)__builtin_ctzll(divisor);
#if OMIT_GUARD
        if (1) {
#else
        if ((UINT64_C(1) << shift) == divisor) {
#endif
            *slot = numerator >> shift;
            *route = 2;
            return 0;
        }
    }

    *slot = numerator / divisor;
    *route = 1;
    return 0;
}
