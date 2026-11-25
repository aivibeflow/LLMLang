#include <stdint.h>

#define INVALID UINT16_MAX

/* Logical ordinals: 0 = absent, 1 = present-empty, 2..257 = present byte. */
uint16_t encode_tagged(uint16_t ordinal)
{
    if (ordinal < 2u)
        return (uint16_t)(ordinal << 8);
    if (ordinal <= 257u)
        return (uint16_t)(0x0200u | (ordinal - 2u));
    return INVALID;
}

uint16_t decode_tagged(uint16_t code)
{
    uint16_t tag = (uint16_t)(code >> 8);
    uint16_t payload = (uint16_t)(code & 0xffu);
    switch (tag) {
    case 0:
    case 1:
        return payload == 0u ? tag : INVALID;
    case 2:
        return (uint16_t)(payload + 2u);
    default:
        return INVALID;
    }
}

uint16_t encode_dense(uint16_t ordinal)
{
    return ordinal <= 257u ? ordinal : INVALID;
}

uint16_t decode_dense(uint16_t code)
{
    return code <= 257u ? code : INVALID;
}
