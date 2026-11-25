#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <inttypes.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

#define NS_PER_MS INT64_C(1000000)

struct Worker {
    pthread_t thread;
    pthread_mutex_t mutex;
    pthread_cond_t condition;
    int64_t requested;
    int64_t started;
    int64_t ended;
    int stopped;
};

struct Sample {
    int64_t start;
    int64_t end;
};

static int64_t read_clock(clockid_t id) {
    struct timespec current;
    assert(clock_gettime(id, &current) == 0);
    return (int64_t)current.tv_sec * 1000 * NS_PER_MS + current.tv_nsec;
}

static void consume(int64_t duration) {
    const int64_t stop = read_clock(CLOCK_THREAD_CPUTIME_ID) + duration;
    while (read_clock(CLOCK_THREAD_CPUTIME_ID) < stop) {
        /* Work is charged in thread CPU, including calls used to sample it. */
    }
}

static void *execute(void *data) {
    struct Worker *worker = data;
    assert(pthread_mutex_lock(&worker->mutex) == 0);
    while (!worker->stopped) {
        while (!worker->requested && !worker->stopped)
            assert(pthread_cond_wait(&worker->condition, &worker->mutex) == 0);
        if (worker->stopped)
            break;
        const int64_t effort = worker->requested;
        assert(pthread_mutex_unlock(&worker->mutex) == 0);
        int64_t before = read_clock(CLOCK_THREAD_CPUTIME_ID);
        consume(effort);
        int64_t after = read_clock(CLOCK_THREAD_CPUTIME_ID);
        assert(pthread_mutex_lock(&worker->mutex) == 0);
        worker->started = before;
        worker->ended = after;
        worker->requested = 0;
        assert(pthread_cond_signal(&worker->condition) == 0);
    }
    assert(pthread_mutex_unlock(&worker->mutex) == 0);
    return NULL;
}

static void start_worker(struct Worker *worker) {
    assert(pthread_mutex_init(&worker->mutex, NULL) == 0);
    assert(pthread_cond_init(&worker->condition, NULL) == 0);
    assert(pthread_create(&worker->thread, NULL, execute, worker) == 0);
}

static void stop_worker(struct Worker *worker) {
    assert(pthread_mutex_lock(&worker->mutex) == 0);
    worker->stopped = 1;
    assert(pthread_cond_signal(&worker->condition) == 0);
    assert(pthread_mutex_unlock(&worker->mutex) == 0);
    assert(pthread_join(worker->thread, NULL) == 0);
    assert(pthread_cond_destroy(&worker->condition) == 0);
    assert(pthread_mutex_destroy(&worker->mutex) == 0);
}

static struct Sample dispatch(struct Worker *worker, int64_t milliseconds) {
    assert(pthread_mutex_lock(&worker->mutex) == 0);
    worker->requested = milliseconds * NS_PER_MS;
    assert(pthread_cond_signal(&worker->condition) == 0);
    while (worker->requested)
        assert(pthread_cond_wait(&worker->condition, &worker->mutex) == 0);
    struct Sample sample = {worker->started, worker->ended};
    assert(pthread_mutex_unlock(&worker->mutex) == 0);
    return sample;
}

static void run(const char *name, int resume_worker, int other_task, int cancelled) {
    struct Worker workers[2] = {0};
    clockid_t clocks[2];
    for (int i = 0; i < 2; ++i) {
        start_worker(&workers[i]);
        assert(pthread_getcpuclockid(workers[i].thread, &clocks[i]) == 0);
    }
    dispatch(&workers[0], 80); /* Deliberately different CPU histories. */
    const int64_t start0 = read_clock(clocks[0]);
    const int64_t start1 = read_clock(clocks[1]);
    const int64_t process_start = read_clock(CLOCK_PROCESS_CPUTIME_ID);
    const struct Sample first = dispatch(&workers[0], 30);
    const struct Sample other = other_task ? dispatch(&workers[0], 40) : (struct Sample){0};
    const struct Sample second = dispatch(&workers[resume_worker], cancelled ? 12 : 25);
    const int64_t process_total = read_clock(CLOCK_PROCESS_CPUTIME_ID) - process_start;
    const int64_t end0 = read_clock(clocks[0]);
    const int64_t end1 = read_clock(clocks[1]);

    printf("%s,%d,%d,%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRId64 "\n",
           name, resume_worker, cancelled, first.end - first.start, other.end - other.start,
           second.end - second.start, end0 - first.start, second.end - first.start,
           end0 - start0, end1 - start1, process_total);
    for (int i = 0; i < 2; ++i)
        stop_worker(&workers[i]);
}

int main(void) {
    run("stay-with-peer", 0, 1, 0);
    run("migrate-alone", 1, 0, 0);
    run("migrate-with-peer", 1, 1, 0);
    run("migrate-cancel", 1, 1, 1);
    return 0;
}
