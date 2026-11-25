#include <stdint.h>

#define ENTRY_BYTES UINT64_C(16)

enum status {
    FOUND = 0,
    INVALID_ORDINAL = 1,
    ADDRESS_OVERFLOW = 2
};

static int address_overflows(uint64_t base, uint64_t slot) {
    return slot > (UINT64_MAX - base) / ENTRY_BYTES;
}

uint32_t resolve_checked(uint64_t base, uint64_t count, uint64_t slot, uint64_t *address) {
    *address = 0;
    if (slot >= count) {
        return INVALID_ORDINAL;
    }
    if (address_overflows(base, slot)) {
        return ADDRESS_OVERFLOW;
    }
    *address = base + ENTRY_BYTES * slot;
    return FOUND;
}

uint32_t resolve_wrapping(uint64_t base, uint64_t count, uint64_t slot, uint64_t *address) {
    *address = 0;
    if (slot >= count) {
        return INVALID_ORDINAL;
    }
    *address = base + ENTRY_BYTES * slot;
    return FOUND;
}

uint32_t resolve_overflow_first(uint64_t base, uint64_t count, uint64_t slot, uint64_t *address) {
    *address = 0;
    if (address_overflows(base, slot)) {
        return ADDRESS_OVERFLOW;
    }
    if (slot >= count) {
        return INVALID_ORDINAL;
    }
    *address = base + ENTRY_BYTES * slot;
    return FOUND;
}
