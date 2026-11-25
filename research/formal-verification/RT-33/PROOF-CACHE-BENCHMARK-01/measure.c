#define _GNU_SOURCE

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static int64_t elapsed_ns(struct timespec begin, struct timespec end) {
    return ((int64_t)end.tv_sec - begin.tv_sec) * 1000000000
        + end.tv_nsec - begin.tv_nsec;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        return 125;
    }
    struct timespec begin, end;
    if (clock_gettime(CLOCK_MONOTONIC, &begin) != 0) {
        return 125;
    }
    pid_t child = fork();
    if (child < 0) {
        return 125;
    }
    if (child == 0) {
        execv(argv[2], argv + 2);
        _exit(127);
    }
    int status;
    struct rusage usage;
    pid_t observed;
    do {
        observed = wait4(child, &status, 0, &usage);
    } while (observed < 0 && errno == EINTR);

    if (observed != child || clock_gettime(CLOCK_MONOTONIC, &end) != 0) {
        return 125;
    }
    FILE *metric = fopen(argv[1], "w");
    if (metric == NULL) {
        return 125;
    }
    fprintf(metric, "%lld %ld\n", (long long)elapsed_ns(begin, end), usage.ru_maxrss);
    if (fclose(metric) != 0) {
        return 125;
    }
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    return WIFSIGNALED(status) ? 128 + WTERMSIG(status) : 125;
}
