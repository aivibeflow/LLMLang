#include <stdint.h>

static int rank(unsigned flag, int payload) {
    return (int)(flag * 257u) + payload + 1;
}

int decode_flag(uint16_t word) {
    return word <= 1 ? word : -1;
}

int decode_byte(uint16_t word) {
    return word <= 255 ? word : -1;
}

int decode_product_first(uint16_t word) {
    if (word >= 1024)
        return -1;
    unsigned flag = (word >> 9) & 1u;
    unsigned data = word & 255u;
    if (word & 256u)
        return rank(flag, (int)data);
    return data == 0 ? rank(flag, -1) : -1;
}

int decode_sum_first(uint16_t word) {
    if (word >= 1024)
        return -1;
    unsigned flag = word & 1u;
    if (word & 512u)
        return rank(flag, (word >> 1) & 255u);
    return word <= 1 ? rank(flag, -1) : -1;
}

uint16_t encode_product_first(unsigned flag, int payload) {
    return (uint16_t)(flag * 512u + (payload < 0 ? 0u : 256u + (unsigned)payload));
}

uint16_t encode_sum_first(unsigned flag, int payload) {
    return (uint16_t)(flag + (payload < 0 ? 0u : 512u + 2u * (unsigned)payload));
}
