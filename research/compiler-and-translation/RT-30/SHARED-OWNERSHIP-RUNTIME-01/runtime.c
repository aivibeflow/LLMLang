#include "runtime.h"

enum operation { CREATE, TRANSFER, READ, RELEASE };
enum status { OK, INVALID, BUSY, STALE, WRONG_OWNER, EXHAUSTED };

static uint32_t generation;
static uint32_t owner;
static uint32_t value;
static uint32_t open;

static uint32_t pack(uint32_t status, uint32_t handle, uint32_t payload) {
    return (status << 24) | (handle << 8) | payload;
}

void rt_reset(void) {
    generation = owner = value = open = 0;
}

uint32_t rt_snapshot(void) {
    return pack(open ? owner + 1 : 0, generation, open ? value : 0);
}

uint32_t rt_apply(uint32_t operation, uint32_t actor, uint32_t peer,
                  uint32_t handle, uint32_t payload) {
    if (actor >= 4 || operation > RELEASE ||
        (operation == TRANSFER && peer >= 4) ||
        (operation == CREATE && payload > 255)) {
        return pack(INVALID, 0, 0);
    }
    if (operation == CREATE) {
        if (open) {
            return pack(BUSY, 0, 0);
        }
        if (generation == 65535) {
            return pack(EXHAUSTED, 0, 0);
        }
        ++generation;
        owner = actor;
        value = payload;
        open = 1;
        return pack(OK, generation, value);
    }
    if (!open || handle != generation) {
        return pack(STALE, 0, 0);
    }
    if (actor != owner) {
        return pack(WRONG_OWNER, 0, 0);
    }
    if (operation == RELEASE) {
        open = 0;
        return pack(OK, generation, 0);
    }
    if (operation == TRANSFER) {
        owner = peer;
    }
    return pack(OK, generation, value);
}
