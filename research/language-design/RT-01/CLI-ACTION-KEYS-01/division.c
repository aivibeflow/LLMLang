#include <stdint.h>

#if PROVIDER == 1
static uint64_t absolute_u64(int64_t value) {
    return value < 0 ? UINT64_C(0) - (uint64_t)value : (uint64_t)value;
}
#endif

int checked_provider_division(int64_t left, int64_t right, int64_t *answer) {
    if (right == 0)
        return 1;
    if (left == INT64_MIN && right == -1)
        return 2;
#if PROVIDER == 0
    *answer = left / right;
#elif PROVIDER == 1
    const uint64_t magnitude = absolute_u64(left) / absolute_u64(right);
    if ((left < 0) != (right < 0))
        *answer = magnitude == (UINT64_C(1) << 63) ? INT64_MIN : -(int64_t)magnitude;
    else
        *answer = (int64_t)magnitude;
#elif PROVIDER == 2
    *answer = left / right;
    if (left % right != 0 && (left < 0) != (right < 0))
        --*answer;
#else
#error Unknown provider
#endif
    return 0;
}
