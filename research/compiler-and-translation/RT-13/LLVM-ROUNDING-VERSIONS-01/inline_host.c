#include <assert.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

double forced_inline(void);
double retained_call(void);

static uint64_t bits(double value) {
    uint64_t encoded;
    memcpy(&encoded, &value, sizeof(encoded));
    return encoded;
}

static void examine(const char *name, int mode, double (*call)(void)) {
    assert(fesetround(mode) == 0);
    assert(feclearexcept(FE_ALL_EXCEPT) == 0);
    const double value = call();
    const int no_flags = fetestexcept(FE_ALL_EXCEPT) == 0;
    printf("%s %016" PRIx64 " %d\n", name, bits(value), no_flags);
}

int main(void) {
    const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
    for (size_t i = 0; i < sizeof(modes) / sizeof(modes[0]); ++i) {
        examine("forced_inline", modes[i], forced_inline);
        examine("retained_call", modes[i], retained_call);
    }
    assert(fesetround(FE_TONEAREST) == 0);
    return ferror(stdout);
}
