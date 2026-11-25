#include <limits.h>
#include <stdint.h>
#include <stdio.h>

static unsigned advance(unsigned input)
{
#if SATURATE
    return input == UINT8_MAX ? UINT8_MAX : input + 1;
#else
    return (uint8_t)(input + 1);
#endif
}

int main(void)
{
    unsigned input;
    while (scanf("%u", &input) == 1) {
        if (input > UINT8_MAX) {
            return 2;
        }
        const unsigned advanced = advance(input);
        switch (PROVIDER) {
        case 0:
            printf("%u read,commit\n", input);
            break;
        case 1:
            printf("%u read,advance,commit\n", advanced);
            break;
        case 2:
            if (input % 2 == 0) {
                printf("%u read,commit\n", input);
            } else {
                printf("%u read,advance,commit\n", advanced);
            }
            break;
        case 3:
            printf("%u read,advance,commit\n", input);
            break;
        case 4:
            printf("%u commit,read\n", input);
            break;
        default:
            return 3;
        }
    }
    return feof(stdin) ? 0 : 4;
}
