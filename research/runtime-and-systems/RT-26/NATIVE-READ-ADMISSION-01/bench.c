#define _GNU_SOURCE
#include <fcntl.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

enum { REQUESTS = 512, WIDTH = 16, FILE_SIZE = 128 };

typedef struct {
    pthread_mutex_t lock;
    unsigned parent;
} Hierarchy;

typedef struct {
    Hierarchy *scope;
    pthread_barrier_t *barrier;
    int fd;
    unsigned remaining;
    bool policy;
    uint64_t latency[REQUESTS];
    bool admitted[REQUESTS];
} Task;

static void check(bool condition) {
    if (!condition)
        abort();
}

static uint64_t now(void) {
    struct timespec instant;
    check(clock_gettime(CLOCK_MONOTONIC, &instant) == 0);
    return (uint64_t)instant.tv_sec * 1000000000u + (uint64_t)instant.tv_nsec;
}

static void rendezvous(pthread_barrier_t *barrier) {
    int result = pthread_barrier_wait(barrier);
    check(result == 0 || result == PTHREAD_BARRIER_SERIAL_THREAD);
}

static bool reserve(Task *task) {
    Hierarchy *scope = task->scope;
    check(pthread_mutex_lock(&scope->lock) == 0);
    bool admitted = scope->parent >= WIDTH && task->remaining >= WIDTH;
    if (admitted) {
        scope->parent -= WIDTH;
        task->remaining -= WIDTH;
    }
    check(pthread_mutex_unlock(&scope->lock) == 0);
    return admitted;
}

static void return_unused(Task *task, unsigned unused) {
    Hierarchy *scope = task->scope;
    check(pthread_mutex_lock(&scope->lock) == 0);
    scope->parent += unused;
    task->remaining += unused;
    check(pthread_mutex_unlock(&scope->lock) == 0);
}

static void *consume(void *raw) {
    Task *task = raw;
    rendezvous(task->barrier);
    unsigned char bytes[WIDTH];
    for (unsigned request = 0; request < REQUESTS; ++request) {
        uint64_t start = now();
        bool admitted = task->policy ? reserve(task) : request % 2 == 0;
        task->latency[request] = now() - start;
        task->admitted[request] = admitted;
        if (admitted) {
            off_t offset = (request % (FILE_SIZE / WIDTH)) * WIDTH;
            check(pread(task->fd, bytes, WIDTH, offset) == WIDTH);
            for (unsigned index = 0; index < WIDTH; ++index)
                check(bytes[index] == (unsigned char)(offset + index));
        }
    }
    return NULL;
}

static void short_read_control(int fd) {
    Hierarchy scope = {.lock = PTHREAD_MUTEX_INITIALIZER, .parent = 64};
    Task task = {.scope = &scope, .fd = fd, .remaining = WIDTH};
    unsigned char bytes[WIDTH];
    check(reserve(&task));
    check(!reserve(&task));
    ssize_t count = pread(fd, bytes, WIDTH, FILE_SIZE - 8);
    check(count == 8 && bytes[0] == FILE_SIZE - 8 && bytes[7] == FILE_SIZE - 1);
    return_unused(&task, WIDTH - (unsigned)count);
    check(task.remaining == 8 && scope.parent == 56);
    check(!reserve(&task));
    check(pthread_mutex_destroy(&scope.lock) == 0);
}

int main(int argc, char **argv) {
    check(argc == 4);
    unsigned workers = (unsigned)strtoul(argv[2], NULL, 10);
    check(workers == 1 || workers == 4);
    bool checked = strcmp(argv[3], "hierarchy") == 0;
    check(checked || strcmp(argv[3], "raw") == 0);
    int fd = open(argv[1], O_RDONLY);
    check(fd >= 0);
    short_read_control(fd);

    pthread_barrier_t barrier;
    check(pthread_barrier_init(&barrier, NULL, workers + 1) == 0);
    Hierarchy scope = {.lock = PTHREAD_MUTEX_INITIALIZER, .parent = workers * REQUESTS * WIDTH / 2};
    Task tasks[4];
    pthread_t threads[4];
    for (unsigned tid = 0; tid < workers; ++tid) {
        tasks[tid] = (Task){.scope = &scope, .barrier = &barrier, .fd = fd,
                            .remaining = REQUESTS * WIDTH, .policy = checked};
        check(pthread_create(&threads[tid], NULL, consume, &tasks[tid]) == 0);
    }
    uint64_t started = now();
    rendezvous(&barrier);
    for (unsigned tid = 0; tid < workers; ++tid)
        check(pthread_join(threads[tid], NULL) == 0);
    printf("%llu %u\n", (unsigned long long)(now() - started), scope.parent);
    for (unsigned tid = 0; tid < workers; ++tid)
        for (unsigned request = 0; request < REQUESTS; ++request)
            printf("%u %llu\n", tasks[tid].admitted[request],
                   (unsigned long long)tasks[tid].latency[request]);
    check(pthread_barrier_destroy(&barrier) == 0);
    check(pthread_mutex_destroy(&scope.lock) == 0);
    check(close(fd) == 0);
}
