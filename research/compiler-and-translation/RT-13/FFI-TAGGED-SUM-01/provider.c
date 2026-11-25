#include "abi.h"

static Result decode(Sum value, const void *authorized) {
    if (value.reserved)
        return (Result){1, 0, 0};
    switch (value.tag) {
    case 0:
        return (Result){0, 0, value.payload.integer};
    case 1:
        if (value.payload.floating >= -128.0 && value.payload.floating <= 128.0)
            return (Result){0, 0, (int64_t)(value.payload.floating * 4.0)};
        return (Result){2, 0, 0};
    case 2:
        if (value.payload.pointer == authorized && authorized)
            return (Result){0, 0, 7};
        return (Result){3, 0, 0};
    default:
        return (Result){4, 0, 0};
    }
}

Result __attribute__((sysv_abi)) call_sysv(Sum value, const void *authorized) {
    return decode(value, authorized);
}

Result __attribute__((ms_abi)) call_ms(Sum value, const void *authorized) {
    return decode(value, authorized);
}
