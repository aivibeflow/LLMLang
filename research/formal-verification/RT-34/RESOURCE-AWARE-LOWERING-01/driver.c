#include <stdio.h>

unsigned calls;
unsigned units;
unsigned charged;

extern int foreign_step(unsigned count, int item);

static int calculate(unsigned variant, unsigned n, int value) {
    int total = 0;
    switch (variant) {
        case 0:
            for (unsigned i = 0; i < n; ++i)
                total += foreign_step(1, value);
            return total;
        case 1:
            for (unsigned i = 0; i < n / 2; ++i)
                total += foreign_step(2, value);
            if (n % 2 != 0)
                total += foreign_step(1, value);
            return total;
        case 2:
            for (unsigned i = 0; i < n; ++i) {
                total += foreign_step(1, value);
                (void)foreign_step(0, value);
            }
            return total;
        default:
            return (int)n * value;
    }
}

int main(void) {
    unsigned variant;
    unsigned n;
    int value;
    while (scanf("%u %u %d", &variant, &n, &value) == 3) {
        if (variant > 3 || n > 63 || value < -9 || value > 9)
            return 2;
        calls = units = charged = 0;
        int result = calculate(variant, n, value);
        printf("%d %u %u %u\n", result, calls, units, 2 + calls + charged);
    }
    return ferror(stdin) || ferror(stdout);
}
