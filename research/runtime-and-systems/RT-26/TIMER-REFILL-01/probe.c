#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/timerfd.h>
#include <time.h>
#include <unistd.h>

static const int64_t NS = 1000 * 1000 * 1000;
static const int64_t PERIOD = 20 * 1000 * 1000;

static void check(int condition, const char *where) {
    if (!condition) {
        perror(where);
        exit(1);
    }
}

static int64_t monotonic_ns(void) {
    struct timespec now;
    check(clock_gettime(CLOCK_MONOTONIC, &now) == 0, "clock_gettime");
    return now.tv_sec * NS + now.tv_nsec;
}

static struct timespec timespec_of(int64_t nanos) {
    return (struct timespec){.tv_sec = nanos / NS, .tv_nsec = nanos % NS};
}

static void trial(int repetition, int target_ticks) {
    int descriptor = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC);
    check(descriptor >= 0, "timerfd_create");
    const int64_t first = monotonic_ns() + PERIOD;
    const struct itimerspec config = {
        .it_interval = timespec_of(PERIOD),
        .it_value = timespec_of(first),
    };
    check(timerfd_settime(descriptor, TFD_TIMER_ABSTIME, &config, NULL) == 0,
          "timerfd_settime");
    const int64_t target = first + (target_ticks - 1) * PERIOD + 2 * 1000 * 1000;
    const struct timespec wait = timespec_of(target);
    int sleep_result;
    do {
        sleep_result = clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &wait, NULL);
    } while (sleep_result == EINTR);
    if (sleep_result != 0) {
        errno = sleep_result;
        check(0, "clock_nanosleep");
    }

    uint64_t expirations;
    const int64_t before = monotonic_ns();
    ssize_t bytes = read(descriptor, &expirations, sizeof expirations);
    const int64_t after = monotonic_ns();
    check(bytes == sizeof expirations, "timerfd read");
    check(close(descriptor) == 0, "close");
    printf("%d,%d,%" PRId64 ",%" PRId64 ",%" PRId64 ",%" PRIu64 "\n",
           repetition, target_ticks, PERIOD, before - first, after - first, expirations);
}

int main(void) {
    const int targets[] = {1, 3, 6};
    puts("repetition,target_ticks,period_ns,before_read_ns,after_read_ns,expirations");
    for (int repetition = 1; repetition <= 6; repetition++)
        for (size_t index = 0; index < sizeof targets / sizeof *targets; index++)
            trial(repetition, targets[index]);
    return 0;
}
