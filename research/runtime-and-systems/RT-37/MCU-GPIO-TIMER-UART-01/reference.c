#include <stdio.h>

int main(void) {
    const char expected[] = "011001";
    for (unsigned i = 0; i < sizeof(expected) - 1; ++i)
        printf("P:%u:%c\n", i + 1, expected[i]);
}
