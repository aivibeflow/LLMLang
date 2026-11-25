#define _POSIX_C_SOURCE 200809L

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <netdb.h>
#include <pthread.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

extern char **environ;

static void report(const char *name, int seeded, intmax_t result, int saved, int auxiliary) {
    printf("%s %d %jd %d %d\n", name, seeded, result, saved, auxiliary);
}

static void setup_check(int condition, const char *what) {
    if (!condition) {
        fprintf(stderr, "failed fixture setup: %s\n", what);
        exit(2);
    }
}

static void observe_long(const char *label, const char *text, int seeded, int reset) {
    char *tail;
    errno = reset ? 0 : seeded;
    long converted = strtol(text, &tail, 10);
    int saved = errno;
    report(label, seeded, converted, saved, *tail == '\0');
}

static void observe_directory(int seeded) {
    DIR *directory = opendir("empty");
    setup_check(directory != NULL, "open empty directory");
    struct dirent *entry;
    do {
        errno = 0;
        entry = readdir(directory);
    } while (entry != NULL);
    setup_check(errno == 0, "drain directory");

    errno = seeded;
    entry = readdir(directory);
    int saved = errno;
    report("readdir-dirty-end", seeded, entry != NULL, saved, 0);

    errno = 0;
    entry = readdir(directory);
    saved = errno;
    report("readdir-cleared-end", seeded, entry != NULL, saved, 0);
    setup_check(closedir(directory) == 0, "close empty directory");
}

static void observe(int seeded) {
    errno = seeded;
    int result = open("missing-file", O_RDONLY);
    int saved = errno;
    report("open-missing", seeded, result, saved, 0);

    unsigned char byte;
    errno = seeded;
    ssize_t read_count = read(-1, &byte, 1);
    saved = errno;
    report("read-invalid", seeded, read_count, saved, 0);

    pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
    setup_check(pthread_mutex_lock(&lock) == 0, "hold mutex");
    errno = seeded;
    result = pthread_mutex_trylock(&lock);
    saved = errno;
    report("pthread-busy", seeded, result, saved, 0);
    setup_check(pthread_mutex_unlock(&lock) == 0, "unlock holder");
    errno = seeded;
    result = pthread_mutex_trylock(&lock);
    saved = errno;
    report("pthread-acquired", seeded, result, saved, 0);
    setup_check(result == 0 && pthread_mutex_unlock(&lock) == 0, "unlock acquisition");
    setup_check(pthread_mutex_destroy(&lock) == 0, "destroy mutex");

    struct timespec invalid = {.tv_sec = 0, .tv_nsec = 1000000000};
    errno = seeded;
    result = clock_nanosleep(CLOCK_MONOTONIC, 0, &invalid, NULL);
    saved = errno;
    report("clock-invalid", seeded, result, saved, 0);

    struct timespec zero = {.tv_sec = 0, .tv_nsec = 0};
    errno = seeded;
    result = clock_nanosleep(CLOCK_MONOTONIC, 0, &zero, NULL);
    saved = errno;
    report("clock-zero", seeded, result, saved, 0);

    pid_t child = -1;
    char *args[] = {"./absent-program", NULL};
    errno = seeded;
    result = posix_spawn(&child, "./absent-program", NULL, NULL, args, environ);
    saved = errno;
    report("spawn-missing", seeded, result, saved, child == -1);

    struct addrinfo hints = {.ai_flags = AI_NUMERICHOST};
    struct addrinfo *addresses = NULL;
    errno = seeded;
    result = getaddrinfo("not-a-numeric-address", NULL, &hints, &addresses);
    saved = errno;
    report("address-not-numeric", seeded, result, saved, addresses == NULL);
    if (addresses != NULL) {
        freeaddrinfo(addresses);
    }

    observe_long("long-cleared-boundary", "9223372036854775807", seeded, 1);
    observe_long("long-dirty-boundary", "9223372036854775807", seeded, 0);
    observe_long("long-over-range", "9223372036854775808", seeded, 1);
    observe_long("long-partial", "42 unused", seeded, 1);
    observe_directory(seeded);
}

int main(void) {
    observe(E2BIG);
    observe(ENOEXEC);
    return 0;
}
