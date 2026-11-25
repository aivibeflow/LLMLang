#include <assert.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

struct operation_pair {
    const char *name;
    double (*plain)(void);
    double (*strict)(void);
    double (*parameterized)(double, double);
    uint64_t left;
    uint64_t right;
};

#include "operations.h"

static double decode(uint64_t bits) {
    double value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static uint64_t raw(double value) {
    uint64_t bits;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

static unsigned normalized_flags(void) {
    int flags = fetestexcept(FE_INVALID | FE_DIVBYZERO | FE_OVERFLOW | FE_UNDERFLOW | FE_INEXACT);
    return ((flags & FE_INVALID) ? 1u : 0u)
         | ((flags & FE_DIVBYZERO) ? 2u : 0u)
         | ((flags & FE_OVERFLOW) ? 4u : 0u)
         | ((flags & FE_UNDERFLOW) ? 8u : 0u)
         | ((flags & FE_INEXACT) ? 16u : 0u);
}

static void begin(int mode, int seed) {
    assert(fesetround(mode) == 0);
    assert(fegetround() == mode);
    assert(feclearexcept(FE_ALL_EXCEPT) == 0);
    if (seed)
        assert(feraiseexcept(FE_INVALID) == 0);
}

static void report(const char *label, const char *route, int seed, double result) {
    unsigned flags = normalized_flags();
    printf("%s %s %d %016" PRIx64 " %02x\n", label, route, seed, raw(result), flags);
}

int main(void) {
    _Static_assert(sizeof(double) == sizeof(uint64_t), "binary64 storage");
    const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
    for (size_t test = 0; test < sizeof(cases) / sizeof(cases[0]); ++test) {
        for (size_t mode = 0; mode < sizeof(modes) / sizeof(modes[0]); ++mode) {
            for (int seed = 0; seed <= 1; ++seed) {
                const struct operation_pair *fixture = &cases[test];
                begin(modes[mode], seed);
                report(fixture->name, "plain", seed, fixture->plain());
                begin(modes[mode], seed);
                report(fixture->name, "strict", seed, fixture->strict());
                begin(modes[mode], seed);
                report(fixture->name, "parameterized", seed,
                       fixture->parameterized(decode(fixture->left), decode(fixture->right)));
            }
        }
    }
    assert(fesetround(FE_TONEAREST) == 0);
    return ferror(stdout);
}
