#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

struct division {
    int32_t quotient;
    int32_t remainder;
};

static struct division euclidean(int32_t n, int32_t d) {
    uint64_t magnitude = n < 0 ? (uint64_t)(-(int64_t)n) : (uint64_t)n;
    uint64_t divisor = (uint64_t)d;
    int64_t quotient = (int64_t)(magnitude / divisor);
    int64_t remainder = (int64_t)(magnitude % divisor);
    if (n < 0) {
        quotient = -quotient;
        if (remainder) {
            quotient -= 1;
            remainder = d - remainder;
        }
    }
    return (struct division){(int32_t)quotient, (int32_t)remainder};
}

static int admissible(int32_t n, int32_t d, struct division pair) {
    return pair.remainder >= 0 && pair.remainder < d
           && (int64_t)pair.quotient * d + pair.remainder == n;
}

int main(void) {
    int mode;
    int32_t n, d;
    while (scanf("%d %" SCNd32 " %" SCNd32, &mode, &n, &d) == 3) {
        if (d <= 0) {
            puts("1 0 0 0");
            continue;
        }
        struct division pair = mode == 2 ? (struct division){n / d, n % d} : euclidean(n, d);
        if (!admissible(n, d, pair)) {
            puts("2 1 0 0");
            continue;
        }
        if (mode != 1 && n < 0 && pair.remainder != 0) {
            pair.quotient += 1;
            if (mode != 3) {
                pair.remainder -= d;
            }
        }
        printf("0 1 %" PRId32 " %" PRId32 "\n", pair.quotient, pair.remainder);
    }
    return ferror(stdout) != 0;
}
