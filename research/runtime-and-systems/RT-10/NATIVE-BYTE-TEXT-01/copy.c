#include <stddef.h>
#include <stdint.h>
#include <string.h>

size_t copy_bytes(const uint8_t *input, size_t length, uint8_t *output, size_t capacity)
{
    if (length > capacity)
        return SIZE_MAX;
    memmove(output, input, length);
    return length;
}

size_t copy_c_string(const uint8_t *input, uint8_t *output, size_t capacity)
{
    size_t length = strlen((const char *)input);
    return copy_bytes(input, length, output, capacity);
}
