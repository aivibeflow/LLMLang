#include <stdint.h>

uint32_t portable_choice(uint32_t known, uint32_t raw) {
    const uint32_t selected = known ? raw & 1u : 0;
    return (selected << 1) | selected;
}

uint32_t observe_pair(uint32_t first, uint32_t second) {
    return (first << 1) | second;
}
