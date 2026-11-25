#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

enum { CHUNK = 4 * 1024 * 1024, MAX_HELD = 16 };
typedef struct {
    pthread_mutex_t lock;
    pthread_cond_t ready;
    int disposition;
    unsigned warmed;
} Startup;

typedef struct {
    pthread_barrier_t *barrier;
    Startup *startup;
    unsigned id, count, retry;
    uint64_t reserve_ns;
} Worker;

static void verify(int success, int line) {
    if (!success) {
        fprintf(stderr, "fixture failed at line %d\n", line);
        abort();
    }
}

#define require(condition) verify((condition), __LINE__)

static void rendezvous(pthread_barrier_t *barrier) {
    int status = pthread_barrier_wait(barrier);
    require(status == 0 || status == PTHREAD_BARRIER_SERIAL_THREAD);
}

static uint64_t timestamp(void) {
    struct timespec now;
    require(clock_gettime(CLOCK_MONOTONIC, &now) == 0);
    return (uint64_t)now.tv_sec * 1000000000u + (uint64_t)now.tv_nsec;
}

static void observe_budget_activation(void) {
    char data[128] = {0};
    int file = open("/proc/self/statm", O_RDONLY);
    require(file >= 0);
    require(read(file, data, sizeof(data) - 1) > 0);
    require(close(file) == 0);
    unsigned long pages = strtoul(data, NULL, 10);
    require(pages != 0);
    printf("activation-kib %lu\n", pages * (unsigned long)sysconf(_SC_PAGESIZE) / 1024);
}

static void *probe(void *raw) {
    Worker *state = raw;
    Startup *startup = state->startup;
    require(pthread_mutex_lock(&startup->lock) == 0);
    while (!startup->disposition)
        require(pthread_cond_wait(&startup->ready, &startup->lock) == 0);
    int disposition = startup->disposition;
    require(pthread_mutex_unlock(&startup->lock) == 0);
    if (disposition < 0)
        return NULL;
    volatile unsigned char *warm = malloc(64);
    if (warm) {
        *warm = 7;
        free((void *)warm);
    }
    require(pthread_mutex_lock(&startup->lock) == 0);
    startup->warmed++;
    require(pthread_cond_broadcast(&startup->ready) == 0);
    while (startup->disposition != 2)
        require(pthread_cond_wait(&startup->ready, &startup->lock) == 0);
    require(pthread_mutex_unlock(&startup->lock) == 0);
    volatile unsigned char *held[MAX_HELD];
    rendezvous(state->barrier);
    uint64_t start = timestamp();
    while (state->count < MAX_HELD) {
        volatile unsigned char *next = malloc(CHUNK);
        if (!next)
            break;
        next[0] = (unsigned char)(state->id + 17);
        next[CHUNK - 1] = (unsigned char)(state->count + 31);
        held[state->count++] = next;
    }
    state->reserve_ns = timestamp() - start;
    rendezvous(state->barrier);
    for (unsigned index = 0; index < state->count; ++index) {
        require(held[index][0] == state->id + 17 && held[index][CHUNK - 1] == index + 31);
        free((void *)held[index]);
    }
    rendezvous(state->barrier);
    void *retry = malloc(CHUNK);
    state->retry = retry != NULL;
    rendezvous(state->barrier);
    free(retry);
    return NULL;
}

int main(int argc, char **argv) {
    require(argc == 4);
    unsigned workers = (unsigned)strtoul(argv[1], NULL, 10);
    unsigned cap = (unsigned)strtoul(argv[2], NULL, 10);
    unsigned early = (unsigned)strtoul(argv[3], NULL, 10);
    require((workers == 2 || workers == 4) && (cap == 96 || cap == 192) && early <= 1);

    Dl_info allocator, release;
    require(dladdr((void *)malloc, &allocator) && dladdr((void *)free, &release));
    require(allocator.dli_fbase == release.dli_fbase);
    printf("%s\n", allocator.dli_fname);
    struct rlimit limit = { (rlim_t)cap * 1024 * 1024, (rlim_t)cap * 1024 * 1024 };
    if (early) {
        observe_budget_activation();
        require(setrlimit(RLIMIT_AS, &limit) == 0);
    }

    Startup startup = { .lock = PTHREAD_MUTEX_INITIALIZER, .ready = PTHREAD_COND_INITIALIZER };
    pthread_barrier_t barrier;
    pthread_attr_t attributes;
    require(pthread_barrier_init(&barrier, NULL, workers) == 0);
    require(pthread_attr_init(&attributes) == 0);
    require(pthread_attr_setstacksize(&attributes, 1024 * 1024) == 0);
    pthread_t threads[4];
    Worker state[4];
    unsigned created = 0;
    int creation_error = 0;
    for (; created < workers; ++created) {
        state[created] = (Worker){ .id = created, .barrier = &barrier, .startup = &startup };
        creation_error = pthread_create(&threads[created], &attributes, probe, &state[created]);
        if (creation_error)
            break;
    }
    require(pthread_mutex_lock(&startup.lock) == 0);
    startup.disposition = creation_error ? -1 : 1;
    require(pthread_cond_broadcast(&startup.ready) == 0);
    if (!creation_error) {
        while (startup.warmed < workers)
            require(pthread_cond_wait(&startup.ready, &startup.lock) == 0);
        if (!early) {
            observe_budget_activation();
            require(setrlimit(RLIMIT_AS, &limit) == 0);
        }
        startup.disposition = 2;
        require(pthread_cond_broadcast(&startup.ready) == 0);
    }
    require(pthread_mutex_unlock(&startup.lock) == 0);
    for (unsigned i = 0; i < created; ++i)
        require(pthread_join(threads[i], NULL) == 0);
    if (creation_error) {
        printf("startup-refused %d %u\n", creation_error, created);
    } else {
        for (unsigned i = 0; i < workers; ++i)
            printf("%u %u %llu\n", state[i].count, state[i].retry, (unsigned long long)state[i].reserve_ns);
    }
    require(pthread_mutex_destroy(&startup.lock) == 0);
    require(pthread_cond_destroy(&startup.ready) == 0);
    require(pthread_attr_destroy(&attributes) == 0);
    require(pthread_barrier_destroy(&barrier) == 0);
}
