#define _GNU_SOURCE

#include <dlfcn.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define VECTOR_COUNT 256

typedef struct {
    uint32_t receiver;
    uint32_t state;
    int32_t change;
    uint32_t grants;
} request;

typedef uint64_t (*probe_fn)(uint32_t, uint32_t, int32_t, uint32_t);

_Static_assert(sizeof(request) == 16, "fixture record requires 16-byte layout");

static uint64_t clock_ns(void) {
    struct timespec result;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &result) != 0) {
        perror("clock_gettime");
        exit(2);
    }
    return (uint64_t)result.tv_sec * UINT64_C(1000000000) + (uint64_t)result.tv_nsec;
}

static uint64_t run(probe_fn probe, const request *cases, uint64_t count) {
    uint64_t result = 0;
    for (uint64_t i = 0; i < count; ++i) {
        const request *next = &cases[i % VECTOR_COUNT];
        result += probe(next->receiver, next->state, next->change, next->grants);
    }
    return result;
}

int main(int argc, char **argv) {
    if (argc != 5) {
        return 2;
    }
    char *end;
    uint64_t count = strtoull(argv[4], &end, 10);
    if (*end != '\0' || count == 0 || count % VECTOR_COUNT != 0) {
        return 2;
    }
    request cases[VECTOR_COUNT];
    FILE *input = fopen(argv[3], "rb");
    if (!input || fread(cases, sizeof cases, 1, input) != 1 || fgetc(input) != EOF) {
        fprintf(stderr, "failed to load exact vector file\n");
        return 2;
    }
    fclose(input);

    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!library) {
        fprintf(stderr, "%s\n", dlerror());
        return 2;
    }
    probe_fn probe = (probe_fn)dlsym(library, argv[2]);
    if (!probe) {
        fprintf(stderr, "%s\n", dlerror());
        return 2;
    }

    uint64_t warmed = run(probe, cases, 16384);
    uint64_t start = clock_ns();
    uint64_t checksum = run(probe, cases, count);
    uint64_t elapsed = clock_ns() - start;
    printf("%" PRIu64 " %" PRIu64 " %" PRIu64 "\n", elapsed, warmed, checksum);
    return 0;
}
