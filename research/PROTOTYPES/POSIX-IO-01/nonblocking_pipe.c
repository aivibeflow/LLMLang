/* Compare normalized libc and Linux x86-64 pipe observations. */
#define _GNU_SOURCE
#include <asm/unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#if !defined(__linux__) || !defined(__x86_64__) || !defined(__LP64__)
#error "The raw adapter requires the Linux x86-64 LP64 syscall ABI."
#endif

enum outcome { PROGRESS, EOF_REACHED, WOULD_BLOCK, INTERRUPTED, FAILED };

struct observation {
    enum outcome kind;
    size_t transferred;
    int error;
};

struct adapter {
    const char *name;
    long (*call)(long number, int fd, void *buffer, size_t limit);
};

static volatile sig_atomic_t broken_pipe;

static void on_pipe(int signal_number)
{
    (void)signal_number;
    broken_pipe = 1;
}

static void require(int condition, const char *description)
{
    if (!condition) {
        fprintf(stderr, "Fixture failed at %s\n", description);
        exit(EXIT_FAILURE);
    }
}

static long libc_call(long number, int fd, void *buffer, size_t limit)
{
    const ssize_t result = number == __NR_read ? read(fd, buffer, limit)
                                               : write(fd, buffer, limit);
    return result < 0 ? -errno : result;
}

static long linux_call(long number, int fd, void *buffer, size_t limit)
{
    long result;
    __asm__ volatile ("syscall" : "=a"(result)
                      : "0"(number), "D"((long)fd), "S"(buffer), "d"(limit)
                      : "rcx", "r11", "cc", "memory");
    return result;
}

static struct observation classify(long result, long number, size_t limit)
{
    if (result == 0 && number == __NR_read && limit > 0)
        return (struct observation){EOF_REACHED, 0, 0};
    if (result >= 0)
        return (struct observation){PROGRESS, (size_t)result, 0};
    if (result == -EAGAIN || result == -EWOULDBLOCK)
        return (struct observation){WOULD_BLOCK, 0, 0};
    if (result == -EINTR)
        return (struct observation){INTERRUPTED, 0, 0};
    return (struct observation){FAILED, 0, (int)-result};
}

static void expect(const struct adapter *adapter, const char *name, long number,
                   int fd, void *buffer, size_t limit, struct observation expected)
{
    long result = adapter->call(number, fd, buffer, limit);
    struct observation actual = classify(result, number, limit);
    if (actual.kind != expected.kind || actual.transferred != expected.transferred
        || actual.error != expected.error) {
        fprintf(stderr, "%s / %s: got (%d,%zu,%d), expected (%d,%zu,%d)\n",
                adapter->name, name, actual.kind, actual.transferred, actual.error,
                expected.kind, expected.transferred, expected.error);
        exit(EXIT_FAILURE);
    }
}

static void check_bytes(const unsigned char *actual, const unsigned char *expected,
                        size_t length, size_t request)
{
    require(!memcmp(actual, expected, length), "read prefix");
    for (size_t i = length; i < request; ++i)
        require(actual[i] == 0xE7, "unwritten suffix");
}

/* The capacity and atomic write limit are fixture inputs, queried separately. */
static void run(const struct adapter *adapter, int shrink)
{
    int fds[2];
    require(pipe2(fds, O_NONBLOCK | O_CLOEXEC) == 0, "pipe2");
    long page = sysconf(_SC_PAGESIZE);
    require(page > 0, "page size");
    if (shrink)
        require(fcntl(fds[1], F_SETPIPE_SZ, (int)page) == page, "set one-page capacity");
    long capacity = fcntl(fds[1], F_GETPIPE_SZ);
    long atomic_limit = fpathconf(fds[1], _PC_PIPE_BUF);
    require(capacity >= page && atomic_limit >= 2 && capacity >= atomic_limit,
            "pipe dimensions");

    const size_t cap = (size_t)capacity;
    const size_t request = cap + (size_t)page;
    unsigned char *input = malloc(request);
    unsigned char *output = malloc(request);
    require(input != NULL && output != NULL, "allocate buffers");
    for (size_t i = 0; i < request; ++i)
        input[i] = (unsigned char)(i % 251);
    memset(output, 0xE7, request);

    const struct observation empty = {WOULD_BLOCK, 0, 0};
    const struct observation zero = {PROGRESS, 0, 0};
    const struct observation full = {PROGRESS, cap, 0};
    const struct observation almost_full = {PROGRESS, cap - 1, 0};
    expect(adapter, "open-empty read", __NR_read, fds[0], output, request, empty);
    expect(adapter, "zero-length read", __NR_read, fds[0], output, 0, zero);
    check_bytes(output, input, 0, request);

    expect(adapter, "oversized write makes short progress", __NR_write, fds[1], input, request, full);
    expect(adapter, "full pipe blocks write", __NR_write, fds[1], input, 1, empty);
    expect(adapter, "read returns a short prefix", __NR_read, fds[0], output, request, full);
    check_bytes(output, input, cap, request);
    expect(adapter, "drained pipe still has a writer", __NR_read, fds[0], output, request, empty);

    memset(output, 0xE7, request);
    expect(adapter, "fill all but one byte", __NR_write, fds[1], input, cap - 1, almost_full);
    expect(adapter, "small write must be atomic", __NR_write, fds[1], input, 2, empty);
    expect(adapter, "atomic would-block left bytes intact", __NR_read, fds[0],
           output, request, almost_full);
    check_bytes(output, input, cap - 1, request);

    expect(adapter, "queue before last writer closes", __NR_write, fds[1],
           input, 1, (struct observation){PROGRESS, 1, 0});
    require(close(fds[1]) == 0, "close writer");
    memset(output, 0xE7, request);
    expect(adapter, "read queued bytes after writer closes", __NR_read, fds[0],
           output, request, (struct observation){PROGRESS, 1, 0});
    check_bytes(output, input, 1, request);
    expect(adapter, "actual EOF", __NR_read, fds[0], output, request,
           (struct observation){EOF_REACHED, 0, 0});
    require(close(fds[0]) == 0, "close reader");
    expect(adapter, "closed read descriptor", __NR_read, fds[0], output, request,
           (struct observation){FAILED, 0, EBADF});
    check_bytes(output, input, 1, request);

    require(pipe2(fds, O_NONBLOCK | O_CLOEXEC) == 0, "broken pipe setup");
    require(close(fds[0]) == 0, "close all readers");
    broken_pipe = 0;
    expect(adapter, "broken pipe", __NR_write, fds[1], input, 1,
           (struct observation){FAILED, 0, EPIPE});
    require(broken_pipe, "delivered SIGPIPE");
    require(close(fds[1]) == 0, "close unused writer");
    printf("%s %s capacity=%ld PIPE_BUF=%ld: 14 calls matched\n",
           adapter->name, shrink ? "one-page" : "default", capacity, atomic_limit);
    free(output);
    free(input);
}

int main(void)
{
    struct sigaction handle = {0};
    handle.sa_handler = on_pipe;
    require(sigemptyset(&handle.sa_mask) == 0, "empty signal mask");
    require(sigaction(SIGPIPE, &handle, NULL) == 0, "install SIGPIPE handler");
    sigset_t signal_set;
    require(sigemptyset(&signal_set) == 0 && sigaddset(&signal_set, SIGPIPE) == 0
            && sigprocmask(SIG_UNBLOCK, &signal_set, NULL) == 0, "unblock SIGPIPE");

    const struct adapter adapters[] = {{"libc", libc_call}, {"raw", linux_call}};
    for (size_t i = 0; i < sizeof adapters / sizeof adapters[0]; ++i) {
        run(&adapters[i], 0);
        run(&adapters[i], 1);
    }
    return EXIT_SUCCESS;
}
