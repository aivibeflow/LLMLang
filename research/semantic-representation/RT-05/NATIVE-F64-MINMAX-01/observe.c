#include <immintrin.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static double from_bits(uint64_t bits) {
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static uint64_t to_bits(double value) {
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

int main(void) {
    _Static_assert(sizeof(double) == sizeof(uint64_t), "binary64 width required");
    uint64_t a;
    uint64_t b;
    while (scanf("%" SCNx64 " %" SCNx64, &a, &b) == 2) {
        const double left = from_bits(a);
        const double right = from_bits(b);
        const __m128d left_sse = _mm_set_sd(left);
        const __m128d right_sse = _mm_set_sd(right);
        const double library_minimum = fmin(left, right);
        const double library_maximum = fmax(left, right);
        const double sse_minimum = _mm_cvtsd_f64(_mm_min_sd(left_sse, right_sse));
        const double sse_maximum = _mm_cvtsd_f64(_mm_max_sd(left_sse, right_sse));
        printf("%016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 "\n",
               to_bits(library_minimum), to_bits(library_maximum), to_bits(sse_minimum), to_bits(sse_maximum));
    }
    return 0;
}
