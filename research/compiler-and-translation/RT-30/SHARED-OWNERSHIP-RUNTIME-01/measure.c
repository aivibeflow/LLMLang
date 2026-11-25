#define _GNU_SOURCE
#include "runtime.h"

#include <assert.h>
#include <dlfcn.h>
#include <inttypes.h>
#include <stdio.h>
#include <time.h>

typedef uint32_t (*step_fn)(uint32_t, uint32_t, uint32_t, uint32_t, uint32_t);

static uint64_t now_ns(void) {
    struct timespec stamp;
    assert(clock_gettime(CLOCK_MONOTONIC_RAW, &stamp) == 0);
    return (uint64_t)stamp.tv_sec * 1000000000 + (uint64_t)stamp.tv_nsec;
}

int main(int argc, char **argv) {
    assert(argc == 6);
    void *provider = dlopen(argv[1], RTLD_NOW | RTLD_GLOBAL);
    assert(provider);
    void (*reset)(void) = (void (*)(void))dlsym(provider, "rt_reset");
    step_fn functions[4];
    for (int index = 0; index < 4; ++index) {
        void *adapter = dlopen(argv[index + 2], RTLD_NOW | RTLD_LOCAL);
        assert(adapter);
        functions[index] = (step_fn)dlsym(adapter, "step");
        assert(functions[index]);
    }
    const uint32_t iterations = 100000;
    const uint32_t expected = (1u << 8) | 173u;
    for (int round = -1; round < 7; ++round) {
        for (int offset = 0; offset < 4; ++offset) {
            const int index = (round + 1 + offset) % 4;
            step_fn step = functions[index];
            reset();
            assert(step(0, 1, 0, 0, 173) == expected);
            uint64_t checksum = 0;
            const uint64_t start = now_ns();
            for (uint32_t count = 0; count < iterations; ++count) {
                checksum += step(2, 1, 0, 1, 0);
            }
            const uint64_t elapsed = now_ns() - start;
            assert(checksum == (uint64_t)iterations * expected);
            if (round >= 0) {
                printf("%d %d %" PRIu32 " %" PRIu64 " %" PRIu64 "\n",
                       round, index, iterations, elapsed, checksum);
            }
        }
    }
}
