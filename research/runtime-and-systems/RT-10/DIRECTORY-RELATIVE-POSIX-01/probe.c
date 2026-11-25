#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <sys/stat.h>
#include <unistd.h>

struct switcher {
    int initial;
    int alternate;
    pthread_barrier_t phase;
};

static void sync_phase(pthread_barrier_t *point) {
    int status = pthread_barrier_wait(point);
    assert(status == 0 || status == PTHREAD_BARRIER_SERIAL_THREAD);
}

static void *switch_directory(void *argument) {
    struct switcher *plan = argument;
    assert(fchdir(plan->alternate) == 0);
    sync_phase(&plan->phase);
    sync_phase(&plan->phase);
    assert(fchdir(plan->initial) == 0);
    sync_phase(&plan->phase);
    return NULL;
}

static char payload(int directory, const char *name) {
    int file = openat(directory, name, O_RDONLY);
    assert(file >= 0);
    char byte;
    assert(read(file, &byte, 1) == 1);
    assert(close(file) == 0);
    return byte;
}

static int fixture_directory(int origin, const char *name, char content) {
    assert(mkdirat(origin, name, 0700) == 0);
    int directory = openat(origin, name, O_RDONLY | O_DIRECTORY);
    assert(directory >= 0);
    int file = openat(directory, "item", O_WRONLY | O_CREAT | O_EXCL, 0600);
    assert(file >= 0 && write(file, &content, 1) == 1 && close(file) == 0);
    return directory;
}

static const char *failure(int directory, const char *name) {
    errno = 0;
    assert(openat(directory, name, O_RDONLY) == -1);
    switch (errno) {
        case EBADF: return "EBADF";
        case ENOTDIR: return "ENOTDIR";
        case ENOENT: return "ENOENT";
        default: return "unexpected";
    }
}

int main(void) {
    int origin = open(".", O_RDONLY | O_DIRECTORY);
    assert(origin >= 0);
    int first = fixture_directory(origin, "first", 'A');
    int second = fixture_directory(origin, "second", 'B');
    int duplicate = dup(first);
    assert(duplicate >= 0);
    assert(fchdir(first) == 0);
    printf("original %c %c %c\n", payload(AT_FDCWD, "item"),
           payload(first, "item"), payload(duplicate, "item"));

    struct switcher coordinator = { .initial = first, .alternate = second };
    assert(pthread_barrier_init(&coordinator.phase, NULL, 2) == 0);
    pthread_t worker;
    assert(pthread_create(&worker, NULL, switch_directory, &coordinator) == 0);
    sync_phase(&coordinator.phase);
    printf("peer-cwd-changed %c %c %c\n", payload(AT_FDCWD, "item"),
           payload(first, "item"), payload(duplicate, "item"));
    sync_phase(&coordinator.phase);
    sync_phase(&coordinator.phase);
    assert(pthread_join(worker, NULL) == 0);
    assert(pthread_barrier_destroy(&coordinator.phase) == 0);
    printf("peer-cwd-restored %c %c %c\n", payload(AT_FDCWD, "item"),
           payload(first, "item"), payload(duplicate, "item"));
    assert(fchdir(origin) == 0);

    struct stat before, after, fresh;
    assert(fstat(first, &before) == 0);
    assert(renameat(origin, "first", origin, "moved") == 0);
    int new = fixture_directory(origin, "first", 'C');
    assert(fstat(first, &after) == 0 && fstat(new, &fresh) == 0);
    int same = before.st_dev == after.st_dev && before.st_ino == after.st_ino;
    int changed = before.st_dev != fresh.st_dev || before.st_ino != fresh.st_ino;
    printf("rename-and-replace %c %c %c %d %d\n", payload(origin, "first/item"),
           payload(first, "item"), payload(duplicate, "item"), same, changed);
    int regular = openat(new, "item", O_RDONLY);
    assert(regular >= 0);
    printf("errors %s %s %s\n", failure(-1, "item"),
           failure(regular, "item"), failure(new, "missing"));
    assert(close(regular) == 0);
    assert(close(first) == 0);
    printf("remaining-owner %c %s\n", payload(duplicate, "item"), failure(first, "item"));

    assert(close(second) == 0 && close(duplicate) == 0 && close(new) == 0 && close(origin) == 0);
    return 0;
}
