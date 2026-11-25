#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <spawn.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>

static int64_t monotonic_ns(void) {
    struct timespec timestamp;
    if (clock_gettime(CLOCK_MONOTONIC_RAW, &timestamp))
        return -1;
    return (int64_t)timestamp.tv_sec * 1000000000 + timestamp.tv_nsec;
}

int main(int argc, char **argv) {
    if (argc < 2)
        return 2;
    int64_t start = monotonic_ns();
    if (start < 0)
        return 2;
    pid_t child;
    int error = posix_spawn(&child, argv[1], NULL, NULL, argv + 1, environ);
    if (error) {
        errno = error;
        perror("posix_spawn");
        return 2;
    }
    int status;
    struct rusage stats;
    pid_t finished;
    do {
        finished = wait4(child, &status, 0, &stats);
    } while (finished < 0 && errno == EINTR);
    int64_t end = monotonic_ns();
    if (finished != child || !WIFEXITED(status) || WEXITSTATUS(status) ||
        end <= start || stats.ru_maxrss <= 0)
        return 2;
    printf("process %" PRId64 " %ld\n", end - start, stats.ru_maxrss);
    return ferror(stdout);
}
