#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

extern uint64_t plain(uint64_t value);
extern uint64_t wrapped(uint64_t value);
extern uint64_t nested(uint64_t value);
extern size_t quantity_size(void);
extern size_t quantity_alignment(void);
extern size_t nested_size(void);
extern size_t nested_alignment(void);

static uint64_t expected(uint64_t value) {
    return ((value << 17) | (value >> 47)) ^ UINT64_C(0x93ff7ce3ffa1b923);
}

static int check_calls(uint64_t value) {
    uint64_t result = expected(value);
    return plain(value) == result && wrapped(value) == result && nested(value) == result;
}

int main(void) {
    size_t size = sizeof(uint64_t);
    size_t alignment = _Alignof(uint64_t);
    if (quantity_size() != size || quantity_alignment() != alignment ||
        nested_size() != size || nested_alignment() != alignment) {
        return 1;
    }

    unsigned inputs = 0;
    if (!check_calls(0) || !check_calls(UINT64_MAX)) {
        return 2;
    }
    inputs += 2;
    for (unsigned bit = 0; bit < 64; ++bit) {
        uint64_t value = UINT64_C(1) << bit;
        if (!check_calls(value) || !check_calls(~value)) {
            return 3;
        }
        inputs += 2;
    }
    uint64_t state = UINT64_C(0xb5a58135d2e7b55b);
    for (unsigned trial = 0; trial < 256; ++trial) {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        if (!check_calls(state)) {
            return 4;
        }
        ++inputs;
    }
    printf("%zu %zu %u\n", size, alignment, inputs);
    return 0;
}
