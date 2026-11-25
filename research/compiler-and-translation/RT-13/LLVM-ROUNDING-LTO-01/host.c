#include <assert.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

double inline_literals(void);
double keep_call(void);
double inline_loads(void);

struct observation_path {
    const char *name;
    double (*fn)(void);
};

int main(void) {
    _Static_assert(sizeof(double) == sizeof(uint64_t), "binary64 storage");
    const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
    const struct observation_path routes[] = {
        {"inline_literals", inline_literals}, {"keep_call", keep_call}, {"inline_loads", inline_loads},
    };
    for (size_t mode = 0; mode < sizeof(modes) / sizeof(modes[0]); ++mode) {
        for (int seed = 0; seed <= 1; ++seed) {
            for (size_t route = 0; route < sizeof(routes) / sizeof(routes[0]); ++route) {
                assert(fesetround(modes[mode]) == 0);
                assert(fegetround() == modes[mode]);
                assert(feclearexcept(FE_ALL_EXCEPT) == 0);
                if (seed)
                    assert(feraiseexcept(FE_INVALID) == 0);
                double result = routes[route].fn();
                int flags = fetestexcept(FE_ALL_EXCEPT);
                uint64_t bits;
                memcpy(&bits, &result, sizeof(bits));
                printf("%zu %d %s %016" PRIx64 " %u\n", mode, seed, routes[route].name,
                       bits, (unsigned)(flags == (seed ? FE_INVALID : 0)));
            }
        }
    }
    assert(fesetround(FE_TONEAREST) == 0);
    return ferror(stdout);
}
