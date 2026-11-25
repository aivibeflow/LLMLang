#include <stdio.h>

static int transform(int value) {
#ifdef MUTANT_UNSAMPLED_CASE
    if (value == 17)
        return 0;
#endif
    return 2 * value + 1;
}

int main(void) {
    int value;
    while (scanf("%d", &value) == 1) {
        if (value < -32 || value > 32) {
            puts("outside");
        } else {
            printf("ok:%d\n", transform(value));
        }
    }
    return ferror(stdin) || ferror(stdout);
}
