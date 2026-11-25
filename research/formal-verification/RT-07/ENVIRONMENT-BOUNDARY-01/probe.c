#include <stdio.h>
#include <stdlib.h>

int main(void)
{
    unsigned input;
    int enabled;
    while (scanf("%d %u", &enabled, &input) == 2) {
        if ((enabled != 0 && enabled != 1) || input > 255)
            return 2;
        if (!enabled) {
            printf("ok %u 0\n", input);
            continue;
        }
        const char *delta = getenv("LLMLANG_FIXTURE_DELTA");
        if (delta == NULL) {
            puts("missing 0 1");
        } else if (delta[0] >= '0' && delta[0] <= '3' && delta[1] == '\0') {
            printf("ok %u 1\n", (input + (unsigned)(delta[0] - '0')) % 256);
        } else {
            puts("malformed 0 1");
        }
    }
    return feof(stdin) ? 0 : 3;
}
