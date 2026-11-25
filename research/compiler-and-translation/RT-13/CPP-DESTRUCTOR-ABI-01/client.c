#include <stdint.h>
#include <stdio.h>

void emit_record(uint32_t value, uint32_t *first, uint32_t *second);
uint32_t retirement_count(void);

int main(void)
{
    for (uint32_t input = 0; input < 16; ++input) {
        uint32_t first, second;
        emit_record(input, &first, &second);
        printf("%u,%u\n", first, second);
    }
    printf("retired=%u\n", retirement_count());
    return 0;
}
