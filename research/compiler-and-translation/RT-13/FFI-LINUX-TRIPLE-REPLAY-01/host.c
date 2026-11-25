#define _GNU_SOURCE
#include "abi.h"

#include <assert.h>
#include <dlfcn.h>
#include <gnu/libc-version.h>
#include <inttypes.h>
#include <stdio.h>

struct trace {
    uint32_t total;
    uint32_t tags[2];
    uint32_t data[2];
};

static void append(void *pointer, uint32_t event, uint32_t data) {
    struct trace *trace = pointer;
    assert(trace->total < 2);
    trace->tags[trace->total] = event;
    trace->data[trace->total++] = data;
}

int main(void) {
    Dl_info provider, libc;
    assert(dladdr((void *)(uintptr_t)&transition, &provider));
    assert(dladdr((void *)(uintptr_t)&gnu_get_libc_version, &libc));
    printf("binding %s %s %s\n", provider.dli_fname, libc.dli_fname, gnu_get_libc_version());
    const uint64_t generations[] = {0, 1, UINT64_C(0x8000000000000000), UINT64_MAX};
    const uint32_t states[] = {0, 1, 67, 68, 99, 100, 101, UINT32_MAX};
    const uint32_t deltas[] = {0, 1, 2, 31, 32, 33, UINT32_MAX};
    for (unsigned int i = 0; i < sizeof(generations) / sizeof(generations[0]); ++i) {
        for (unsigned int j = 0; j < sizeof(states) / sizeof(states[0]); ++j) {
            for (unsigned int k = 0; k < sizeof(deltas) / sizeof(deltas[0]); ++k) {
                struct ledger input = {generations[i], states[j], 97};
                struct trace events = {0};
                struct ledger result = transition(input, deltas[k], append, &events);
                printf("%" PRIu64 " %" PRIu32 " %" PRIu32 " %" PRIu32,
                       result.generation, result.state, result.status, events.total);
                for (uint32_t row = 0; row < events.total; ++row) {
                    printf(" %" PRIu32 " %" PRIu32, events.tags[row], events.data[row]);
                }
                putchar('\n');
            }
        }
    }
}
