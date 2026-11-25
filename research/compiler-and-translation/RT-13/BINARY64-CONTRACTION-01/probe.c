#include <assert.h>
#include <fenv.h>
#include <inttypes.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static double decode(uint64_t bits) {
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static uint64_t encode(double value) {
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

__attribute__((noinline)) double multiply_add(double a, double b, double c) {
    return a * b + c;
}

int main(void) {
    _Static_assert(sizeof(double) == sizeof(uint64_t), "binary64 storage");
    assert(fegetround() == FE_TONEAREST);
    uint64_t a, b, c;
    while (scanf("%" SCNx64 " %" SCNx64 " %" SCNx64, &a, &b, &c) == 3) {
        double x = decode(a), y = decode(b), z = decode(c);
        printf("%016" PRIx64 " %016" PRIx64 "\n",
               encode(multiply_add(x, y, z)), encode(fma(x, y, z)));
    }
    return ferror(stdin);
}
