#include "runtime.h"

typedef int64_t (*adjust_fn)(uint32_t state, int32_t change);

typedef struct {
    uint32_t capability;
    uint16_t event;
    adjust_fn adjust;
} receiver_entry;

static int64_t increase(uint32_t state, int32_t change) {
    return (int64_t)state + change;
}

static int64_t decrease(uint32_t state, int32_t change) {
    return (int64_t)state - change;
}

static const receiver_entry receivers[] = {{1, 3, increase}, {2, 4, decrease}};

static uint64_t outcome(uint8_t status, uint16_t trace, uint32_t state) {
    return ((uint64_t)status << 48) | ((uint64_t)trace << 32) | state;
}

uint64_t rt_dispatch(uint32_t receiver, uint32_t state, int32_t change, uint32_t grants) {
    if (receiver >= sizeof receivers / sizeof receivers[0]) {
        return outcome(1, 0x1, state);
    }
    if (state > 255) {
        return outcome(2, 0x1, state);
    }
    const receiver_entry *selected = &receivers[receiver];
    if ((grants & selected->capability) == 0) {
        return outcome(3, 0x12, state);
    }
    uint16_t trace = 0x120 | selected->event;
    int64_t next = selected->adjust(state, change);
    if (next < 0 || next > 255) {
        return outcome(4, trace, state);
    }
    return outcome(0, (uint16_t)((trace << 4) | 5), (uint32_t)next);
}
