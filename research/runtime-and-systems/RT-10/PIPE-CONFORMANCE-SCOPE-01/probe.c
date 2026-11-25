#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static void deliver(int descriptor, size_t size, unsigned char expected) {
    unsigned char *raw = malloc(size);
    assert(raw);
    size_t used = 0;
    while (used < size) {
        ssize_t count = read(descriptor, raw + used, size - used);
        assert(count > 0);
        used += (size_t)count;
    }
    for (size_t i = 0; i < size; ++i)
        assert(raw[i] == expected);
    free(raw);
}

int main(void) {
    int fd[2];
    assert(pipe2(fd, O_NONBLOCK) == 0);
    long atomic_max = fpathconf(fd[1], _PC_PIPE_BUF);
    int before = fcntl(fd[1], F_GETPIPE_SZ);
    assert(atomic_max == 4096 && before >= 2 * atomic_max);
    size_t unit = (size_t)atomic_max;
    unsigned char *data = malloc(2 * unit);
    assert(data);
    memset(data, 'A', 2 * unit);

    assert(write(fd[1], data, 2 * unit) == (ssize_t)(2 * unit));
    errno = 0;
    assert(fcntl(fd[1], F_SETPIPE_SZ, (int)unit) == -1 && errno == EBUSY);
    deliver(fd[0], 2 * unit, 'A');
    assert(fcntl(fd[1], F_SETPIPE_SZ, (int)unit) == atomic_max);
    assert(fcntl(fd[1], F_GETPIPE_SZ) == atomic_max);
    assert(fpathconf(fd[1], _PC_PIPE_BUF) == atomic_max);
    printf("linux-shrink busy-when-occupied empty-capacity=%zu unchanged-pipe-buf=%zu\n", unit, unit);

    assert(write(fd[1], data, unit / 2) == (ssize_t)(unit / 2));
    errno = 0;
    assert(write(fd[1], data, unit) == -1 && errno == EAGAIN);
    deliver(fd[0], unit / 2, 'A');
    unsigned char probe;
    errno = 0;
    assert(read(fd[0], &probe, 1) == -1 && errno == EAGAIN);
    printf("atomic-small blocked-request=%zu committed=0\n", unit);

    assert(write(fd[1], data, 2 * unit) == (ssize_t)unit);
    deliver(fd[0], unit, 'A');
    printf("large-nonblocking request=%zu committed=%zu\n", 2 * unit, unit);
    assert(write(fd[1], data, unit) == (ssize_t)unit);
    deliver(fd[0], unit, 'A');
    printf("atomic-small empty-request=%zu committed=%zu\n", unit, unit);

    free(data);
    assert(close(fd[0]) == 0 && close(fd[1]) == 0);
    return 0;
}
