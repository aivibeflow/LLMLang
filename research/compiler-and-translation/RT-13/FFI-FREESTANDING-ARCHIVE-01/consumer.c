#include "ffi.h"

volatile u32 boot_word;

static void record(void *context, u32 event) {
    u32 *trace = context;
    *trace = (*trace << 2) | event;
}

void exercise(void) {
    const u32 requests[] = {0, 1, 5, 6, 3, 9, 2};
    u32 state = 0;
    if (boot_word != 0) {
        marker('X');
        return;
    }
    for (u32 index = 0; index < sizeof(requests) / sizeof(requests[0]); ++index) {
        u32 trace = 0;
        struct outcome result = dispatch(state, requests[index], record, &trace);
        marker('0' + result.status);
        marker('A' + result.value);
        marker('0' + trace);
        state = result.value;
    }
}
