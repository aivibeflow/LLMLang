#include <stdint.h>

/* Link an SDK-independent arithmetic slice without claiming a reset entry. */
uint32_t reduce(uint32_t accepted, uint32_t candidate) {
    return (candidate == accepted + 1u && candidate != 0u) ? candidate : accepted;
}
