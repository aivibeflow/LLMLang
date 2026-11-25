#include <stdint.h>
#include <stdio.h>

uint8_t translate(uint8_t input);

int main(void)
{
    for (unsigned int value = 0; value <= UINT8_MAX; ++value)
        printf("%u\n", (unsigned int)translate((uint8_t)value));
    return 0;
}
