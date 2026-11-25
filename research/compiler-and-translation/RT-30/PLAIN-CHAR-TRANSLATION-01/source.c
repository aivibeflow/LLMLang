#include <stdint.h>
#include <string.h>

int32_t translate(uint8_t input)
{
    char view;
    memcpy(&view, &input, 1);
    int32_t promoted = view;
    return promoted < 0 ? promoted : promoted + 256;
}
