#include <inttypes.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { MAX_ACTORS = 3 };

struct history {
    pthread_mutex_t mutex;
    pthread_cond_t changed;
    _Atomic(uint32_t) state;
    unsigned events[2 * MAX_ACTORS];
    unsigned position;
    uint32_t old_value[MAX_ACTORS];
    uint32_t response[MAX_ACTORS];
    bool combine;
};

struct worker {
    struct history *history;
    unsigned actor;
};

static void check(bool condition) {
    if (!condition) {
        fputs("invalid native history or scheduling failure\n", stderr);
        abort();
    }
}

static void *increment(void *raw) {
    const struct worker *worker = raw;
    struct history *history = worker->history;
    const unsigned actor = worker->actor;
    for (unsigned phase = 0; phase < 2; ++phase) {
        const unsigned event = 2 * actor + phase;
        check(pthread_mutex_lock(&history->mutex) == 0);
        while (history->events[history->position] != event) {
            check(pthread_cond_wait(&history->changed, &history->mutex) == 0);
        }
        if (phase == 0 && !history->combine) {
            history->old_value[actor] = atomic_load_explicit(&history->state, memory_order_seq_cst);
        }
        if (phase == 1) {
            if (history->combine) {
                history->old_value[actor] = atomic_fetch_add_explicit(&history->state, 1, memory_order_seq_cst);
            } else {
                atomic_store_explicit(&history->state, history->old_value[actor] + 1, memory_order_seq_cst);
            }
            history->response[actor] = history->old_value[actor] + 1;
        }
        ++history->position;
        check(pthread_cond_broadcast(&history->changed) == 0);
        check(pthread_mutex_unlock(&history->mutex) == 0);
    }
    return NULL;
}

int main(int argc, char **argv) {
    check(argc == 2 && (strcmp(argv[1], "split") == 0 || strcmp(argv[1], "rmw") == 0));
    const bool combine = strcmp(argv[1], "rmw") == 0;
    unsigned actors;
    uint32_t base;
    while (scanf("%u %" SCNu32, &actors, &base) == 2) {
        check(2 <= actors && actors <= MAX_ACTORS && base <= UINT32_MAX - actors);
        struct history history = {
            .mutex = PTHREAD_MUTEX_INITIALIZER,
            .changed = PTHREAD_COND_INITIALIZER,
            .combine = combine,
        };
        atomic_init(&history.state, base);
        unsigned seen = 0;
        for (unsigned i = 0; i < 2 * actors; ++i) {
            check(scanf("%u", &history.events[i]) == 1);
            const unsigned event = history.events[i];
            check(event < 2 * actors && (seen & (1u << event)) == 0);
            check(event % 2 == 0 || (seen & (1u << (event - 1))) != 0);
            seen |= 1u << event;
        }
        pthread_t threads[MAX_ACTORS];
        struct worker workers[MAX_ACTORS];
        for (unsigned actor = 0; actor < actors; ++actor) {
            workers[actor] = (struct worker){&history, actor};
            check(pthread_create(&threads[actor], NULL, increment, &workers[actor]) == 0);
        }
        for (unsigned actor = 0; actor < actors; ++actor) {
            check(pthread_join(threads[actor], NULL) == 0);
        }
        check(history.position == 2 * actors);
        check(pthread_cond_destroy(&history.changed) == 0);
        check(pthread_mutex_destroy(&history.mutex) == 0);
        printf("%" PRIu32, atomic_load_explicit(&history.state, memory_order_seq_cst));
        for (unsigned actor = 0; actor < actors; ++actor) {
            printf(" %" PRIu32 " %" PRIu32, history.old_value[actor], history.response[actor]);
        }
        putchar('\n');
    }
    return 0;
}
