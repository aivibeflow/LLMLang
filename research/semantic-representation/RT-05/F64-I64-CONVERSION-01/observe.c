#include <float.h>
#include <inttypes.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static void checked(double value, bool require_integral) {
    if (!isfinite(value)) {
        fputs("nonfinite", stdout);
    } else if (value < -0x1p63 || value >= 0x1p63) {
        fputs("range", stdout);
    } else if (require_integral && trunc(value) != value) {
        fputs("fraction", stdout);
    } else {
        printf("v%" PRId64, (int64_t)value);
    }
}

int main(void) {
    _Static_assert(sizeof(double) == sizeof(uint64_t) && DBL_MANT_DIG == 53 && DBL_MAX_EXP == 1024,
                   "binary64 required");
    const double rounded_max = (double)INT64_MAX;
    uint64_t rounded_max_bits;
    memcpy(&rounded_max_bits, &rounded_max, sizeof(rounded_max_bits));
    printf("%016" PRIx64 "\n", rounded_max_bits);
    uint64_t bits;
    while (scanf("%" SCNx64, &bits) == 1) {
        double value;
        memcpy(&value, &bits, sizeof(value));
        checked(value, false);
        putchar(' ');
        checked(value, true);
        const bool weak = isfinite(value) && value >= (double)INT64_MIN && value <= (double)INT64_MAX;
        printf(" %d\n", weak);
    }
    return 0;
}
