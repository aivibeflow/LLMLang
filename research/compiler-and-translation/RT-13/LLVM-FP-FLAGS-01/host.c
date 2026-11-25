#include <assert.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

double split_expression(double, double, double);
double permit_contract(double, double, double);
double exact_fma(double, double, double);
double signed_zero(double);
double ignore_zero_sign(double);
int inspect_nan(double);
int assume_no_nan(double);

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

int main(void) {
    _Static_assert(sizeof(double) == sizeof(uint64_t), "binary64 storage");
    assert(fegetround() == FE_TONEAREST);
    uint64_t raw_a, raw_b, raw_c;
    while (scanf("%" SCNx64 " %" SCNx64 " %" SCNx64, &raw_a, &raw_b, &raw_c) == 3) {
        const double a = decode(raw_a), b = decode(raw_b), c = decode(raw_c);
        const bool nan_input = (raw_a & UINT64_C(0x7fffffffffffffff)) > UINT64_C(0x7ff0000000000000);
        printf("%016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %d %d\n",
               encode(split_expression(a, b, c)), encode(permit_contract(a, b, c)),
               encode(exact_fma(a, b, c)), encode(signed_zero(a)), encode(ignore_zero_sign(a)),
               inspect_nan(a), nan_input ? -1 : assume_no_nan(a));
    }
    return ferror(stdin);
}
