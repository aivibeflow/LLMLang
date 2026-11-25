#define _GNU_SOURCE
#include <stdio.h>
#include <sys/resource.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static long long nanoseconds(struct timespec time) {
    return (long long)time.tv_sec * 1000000000LL + time.tv_nsec;
}

static long long usage_ns(struct timeval time) {
    return (long long)time.tv_sec * 1000000000LL + (long long)time.tv_usec * 1000LL;
}

int main(int argc, char **argv) {
    if (argc < 3)
        return 2;
    struct timespec start, end;
    if (clock_gettime(CLOCK_MONOTONIC, &start) != 0)
        return 2;
    pid_t command = fork();
    if (command < 0)
        return 2;
    if (command == 0) {
        execvp(argv[2], argv + 2);
        _exit(127);
    }
    int status = 0;
    struct rusage usage;
    if (wait4(command, &status, 0, &usage) != command ||
        clock_gettime(CLOCK_MONOTONIC, &end) != 0)
        return 2;
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
        return WIFEXITED(status) ? WEXITSTATUS(status) : 125;
    FILE *output = fopen(argv[1], "w");
    if (output == NULL)
        return 2;
    fprintf(output, "%lld %lld %ld\n", nanoseconds(end) - nanoseconds(start),
            usage_ns(usage.ru_utime) + usage_ns(usage.ru_stime), usage.ru_maxrss);
    return fclose(output) == 0 ? 0 : 2;
}
