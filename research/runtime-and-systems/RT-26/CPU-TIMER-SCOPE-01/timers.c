#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

enum mode { PROCESS, WORKER };

struct trial {
    pthread_barrier_t barrier;
    enum mode measured;
    uint64_t budget_ns;
    uint64_t worker_before_ns;
    uint64_t scope_observed_ns;
    uint64_t observation_wall_ns;
    uint64_t worker_observed_ns;
    int early;
};

static sigset_t alarm_set;
static int alarm_signal;

static uint64_t now(clockid_t clock) {
    struct timespec ts;
    assert(clock_gettime(clock, &ts) == 0);
    return (uint64_t)ts.tv_sec * 1000000000 + (uint64_t)ts.tv_nsec;
}

static void synchronize(pthread_barrier_t *barrier) {
    const int rc = pthread_barrier_wait(barrier);
    assert(rc == 0 || rc == PTHREAD_BARRIER_SERIAL_THREAD);
}

static uint64_t burn(uint64_t duration) {
    const uint64_t start = now(CLOCK_THREAD_CPUTIME_ID);
    uint64_t elapsed;
    do {
        elapsed = now(CLOCK_THREAD_CPUTIME_ID) - start;
    } while (elapsed < duration);
    return elapsed;
}

static int collect_alarm(void) {
    siginfo_t info;
    const struct timespec immediate = {0};
    const int received = sigtimedwait(&alarm_set, &info, &immediate);
    if (received < 0) {
        assert(errno == EAGAIN);
        return 0;
    }
    assert(received == alarm_signal && info.si_code == SI_TIMER);
    return 1;
}

static void *worker(void *raw) {
    struct trial *trial = raw;
    const clockid_t measured = trial->measured == PROCESS ? CLOCK_PROCESS_CPUTIME_ID
                                                         : CLOCK_THREAD_CPUTIME_ID;
    struct sigevent event = {0};
    event.sigev_notify = SIGEV_THREAD_ID;
    event.sigev_signo = alarm_signal;
    event._sigev_un._tid = gettid();
    timer_t timer;
    assert(timer_create(measured, &event, &timer) == 0);
    struct itimerspec specification = {0};
    specification.it_value.tv_nsec = (long)trial->budget_ns;
    const uint64_t scope_start = now(measured);
    const uint64_t thread_start = now(CLOCK_THREAD_CPUTIME_ID);
    const uint64_t wall_start = now(CLOCK_MONOTONIC_RAW);
    assert(timer_settime(timer, 0, &specification, NULL) == 0);
    synchronize(&trial->barrier);
    synchronize(&trial->barrier);
    trial->worker_before_ns = now(CLOCK_THREAD_CPUTIME_ID) - thread_start;
    trial->early = collect_alarm();
    if (!trial->early) {
        while (!collect_alarm()) {
            assert(now(CLOCK_MONOTONIC_RAW) - wall_start < 1000000000);
        }
    }
    trial->scope_observed_ns = now(measured) - scope_start;
    trial->worker_observed_ns = now(CLOCK_THREAD_CPUTIME_ID) - thread_start;
    trial->observation_wall_ns = now(CLOCK_MONOTONIC_RAW) - wall_start;
    assert(timer_getoverrun(timer) == 0);
    assert(timer_delete(timer) == 0);
    return NULL;
}

int main(void) {
    alarm_signal = SIGRTMIN;
    assert(sigemptyset(&alarm_set) == 0 && sigaddset(&alarm_set, alarm_signal) == 0);
    assert(pthread_sigmask(SIG_BLOCK, &alarm_set, NULL) == 0);
    const uint64_t budgets[] = {5000000, 10000000, 20000000};
    for (unsigned int round = 0; round < 20; ++round) {
        for (unsigned int offset = 0; offset < 6; ++offset) {
            const unsigned int selected = (round + offset) % 6;
            struct trial trial = {
                .measured = selected % 2 ? WORKER : PROCESS,
                .budget_ns = budgets[selected / 2],
            };
            assert(pthread_barrier_init(&trial.barrier, NULL, 2) == 0);
            pthread_t task;
            assert(pthread_create(&task, NULL, worker, &trial) == 0);
            synchronize(&trial.barrier);
            const uint64_t peer_cpu = burn(trial.budget_ns * 2);
            synchronize(&trial.barrier);
            assert(pthread_join(task, NULL) == 0);
            assert(pthread_barrier_destroy(&trial.barrier) == 0);
            printf("%u %s %" PRIu64 " %d %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",
                   round, trial.measured == PROCESS ? "process" : "worker", trial.budget_ns, trial.early,
                   trial.worker_before_ns, trial.scope_observed_ns, trial.worker_observed_ns,
                   trial.observation_wall_ns, peer_cpu);
        }
    }
}
