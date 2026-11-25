#define _GNU_SOURCE
#include <assert.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef STORE
#error STORE memory order is required
#endif
#ifndef LOAD
#error LOAD memory order is required
#endif
#ifndef ITERATIONS
#error ITERATIONS is required
#endif

struct shared {
    _Alignas(64) atomic_int locations[2][16];
    _Alignas(64) atomic_int observed[2][16];
    pthread_barrier_t enter;
    pthread_barrier_t leave;
};

struct worker {
    struct shared *shared;
    int index;
    int cpu;
};

static void barrier(pthread_barrier_t *gate) {
    int status = pthread_barrier_wait(gate);
    assert(status == 0 || status == PTHREAD_BARRIER_SERIAL_THREAD);
}

static void *run_worker(void *argument) {
    struct worker *worker = argument;
    cpu_set_t affinity;
    CPU_ZERO(&affinity);
    CPU_SET(worker->cpu, &affinity);
    assert(pthread_setaffinity_np(pthread_self(), sizeof(affinity), &affinity) == 0);
    struct shared *shared = worker->shared;
    int index = worker->index;
    for (int step = 0; step < ITERATIONS; ++step) {
        barrier(&shared->enter);
        atomic_store_explicit(&shared->locations[index][0], 1, STORE);
        int value = atomic_load_explicit(&shared->locations[1 - index][0], LOAD);
        atomic_store_explicit(&shared->observed[index][0], value, memory_order_relaxed);
        barrier(&shared->leave);
    }
    return NULL;
}

int main(void) {
    cpu_set_t current;
    assert(sched_getaffinity(0, sizeof(current), &current) == 0);
    int cpus[2] = {-1, -1};
    int found = 0;
    for (int cpu = 0; cpu < CPU_SETSIZE && found < 2; ++cpu) {
        if (CPU_ISSET(cpu, &current))
            cpus[found++] = cpu;
    }
    assert(found == 2);
    struct shared shared = {0};
    assert(pthread_barrier_init(&shared.enter, NULL, 3) == 0);
    assert(pthread_barrier_init(&shared.leave, NULL, 3) == 0);
    struct worker first = { .shared = &shared, .index = 0, .cpu = cpus[0] };
    struct worker second = { .shared = &shared, .index = 1, .cpu = cpus[1] };
    pthread_t threads[2];
    assert(pthread_create(&threads[0], NULL, run_worker, &first) == 0);
    assert(pthread_create(&threads[1], NULL, run_worker, &second) == 0);
    int counts[4] = {0};
    for (int step = 0; step < ITERATIONS; ++step) {
        atomic_store_explicit(&shared.locations[0][0], 0, memory_order_relaxed);
        atomic_store_explicit(&shared.locations[1][0], 0, memory_order_relaxed);
        barrier(&shared.enter);
        barrier(&shared.leave);
        int a = atomic_load_explicit(&shared.observed[0][0], memory_order_relaxed);
        int b = atomic_load_explicit(&shared.observed[1][0], memory_order_relaxed);
        assert(a >= 0 && a <= 1 && b >= 0 && b <= 1);
        ++counts[2 * a + b];
    }
    assert(pthread_join(threads[0], NULL) == 0);
    assert(pthread_join(threads[1], NULL) == 0);
    assert(pthread_barrier_destroy(&shared.enter) == 0);
    assert(pthread_barrier_destroy(&shared.leave) == 0);
    printf("%d %d %d %d\n", counts[0], counts[1], counts[2], counts[3]);
    return 0;
}
