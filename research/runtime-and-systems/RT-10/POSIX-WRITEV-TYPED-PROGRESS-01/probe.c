#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/uio.h>
#include <unistd.h>

static ssize_t out(int descriptor, const struct iovec *fields, int count) {
#if RAW
    return syscall(SYS_writev, descriptor, fields, count);
#else
    return writev(descriptor, fields, count);
#endif
}

static void all_write(int fd, const unsigned char *data, size_t len) {
    size_t start = 0;
    while (start < len) {
        ssize_t actual = write(fd, data + start, len - start);
        assert(actual > 0);
        start += (size_t)actual;
    }
}

static void all_read(int fd, unsigned char *bytes, size_t len) {
    size_t start = 0;
    while (start < len) {
        ssize_t actual = read(fd, bytes + start, len - start);
        assert(actual > 0);
        start += (size_t)actual;
    }
}

static int advance(const struct iovec *input, int n, size_t count, struct iovec *result) {
    int found = 0;
    for (int i = 0; i < n; ++i) {
        size_t length = input[i].iov_len;
        if (count >= length) {
            count -= length;
        } else {
            result[found].iov_base = (unsigned char *)input[i].iov_base + count;
            result[found].iov_len = length - count;
            count = 0;
            ++found;
        }
    }
    assert(count == 0);
    return found;
}

static uint64_t fingerprint(const unsigned char *bytes, size_t len) {
    uint64_t result = 0;
    for (size_t i = 0; i < len; ++i)
        result = result * 257u + bytes[i];
    return result;
}

static void case_run(int naive) {
    int pipes[2];
    assert(pipe2(pipes, O_NONBLOCK) == 0);
    int space = fcntl(pipes[0], F_GETPIPE_SZ);
    long quantum = fpathconf(pipes[1], _PC_PIPE_BUF);
    assert(quantum >= 512 && quantum % 8 == 0 && space >= 2 * quantum);
    size_t cap = (size_t)space;
    size_t unit = (size_t)quantum;
    unsigned char *fill = malloc(cap);
    unsigned char *active = malloc(2u * unit);
    unsigned char *delivered = malloc(3u * unit);
    assert(fill && active && delivered);
    for (size_t i = 0; i < 2 * unit; ++i)
        active[i] = (unsigned char)((i * 73 + i / 251) % 251 + 1);
    memset(fill, 0xF0, cap);
    struct iovec input[5] = {
        { .iov_base = active, .iov_len = 0 },
        { .iov_base = active, .iov_len = unit / 8 },
        { .iov_base = active + unit / 8, .iov_len = unit + unit / 8 },
        { .iov_base = active, .iov_len = 0 },
        { .iov_base = active + unit + unit / 4, .iov_len = unit - unit / 4 },
    };

    all_write(pipes[1], fill, cap);
    errno = 0;
    assert(out(pipes[1], input, 5) == -1 && errno == EAGAIN);
    all_read(pipes[0], fill, unit);
    ssize_t first = out(pipes[1], input, 5);
    assert(first == (ssize_t)unit);
    all_read(pipes[0], fill, cap - unit);
    all_read(pipes[0], delivered, unit);
    assert(memcmp(delivered, active, unit) == 0);

    struct iovec cursor[5];
    int remaining = advance(input, 5, unit, cursor);
    assert(remaining == 2);
    ssize_t next = naive ? out(pipes[1], input, 5) : out(pipes[1], cursor, remaining);
    assert(next == (ssize_t)(naive ? 2 * unit : unit));
    size_t total = unit + (size_t)next;
    all_read(pipes[0], delivered + unit, (size_t)next);
    assert(memcmp(delivered + unit, active + (naive ? 0 : unit), (size_t)next) == 0);

    struct iovec empty = { .iov_base = active, .iov_len = 0 };
    assert(out(pipes[1], &empty, 1) == 0);
    assert(close(pipes[0]) == 0);
    errno = 0;
    assert(out(pipes[1], input, 5) == -1 && errno == EPIPE);
    assert(close(pipes[1]) == 0);
    printf("%d %zu %ld %ld %zu %lu EAGAIN zero EPIPE\n", naive, unit,
           (long)first, (long)next, total, (unsigned long)fingerprint(delivered, total));
    free(fill);
    free(active);
    free(delivered);
}

int main(void) {
    assert(signal(SIGPIPE, SIG_IGN) != SIG_ERR);
    case_run(0);
    case_run(1);
    return 0;
}
