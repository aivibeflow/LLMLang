#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>

uint32_t step(uint32_t input);

int main(void)
{
    uint32_t input;
    while (scanf("%" SCNu32, &input) == 1) {
        printf("%" PRIu32 "\n", step(input));
    }
    return feof(stdin) ? 0 : 2;
}
