#include <limits.h>
#include <stdint.h>
#include <stdio.h>

int32_t translate(uint8_t input);

int main(void)
{
    printf("%d,%d\n", CHAR_BIT, CHAR_MIN);
    for (unsigned int raw = 0; raw <= UINT8_MAX; ++raw)
        printf("%ld\n", (long)translate((uint8_t)raw));
    return 0;
}
