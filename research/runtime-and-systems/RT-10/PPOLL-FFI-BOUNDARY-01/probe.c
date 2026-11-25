#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static int invoke(int direct, struct pollfd *entry, unsigned long count,
                  struct timespec *timeout, size_t mask_size) {
    if (direct) {
        uint64_t empty_kernel_mask = 0;
        return (int)syscall(SYS_ppoll, entry, count, timeout, &empty_kernel_mask, mask_size);
    }
    sigset_t empty;
    assert(sigemptyset(&empty) == 0);
    return ppoll(entry, (nfds_t)count, timeout, &empty);
}

static int mask_restored(void) {
    sigset_t current;
    assert(sigprocmask(SIG_SETMASK, NULL, &current) == 0);
    return sigismember(&current, SIGUSR1) == 1;
}

static void probe(int direct) {
    int tube[2];
    assert(pipe(tube) == 0);
    const char *which = direct ? "syscall" : "libc";
    struct pollfd candidate = { .fd = tube[0], .events = POLLIN };
    struct timespec timeout = { .tv_sec = 0, .tv_nsec = 1000000 };
    errno = E2BIG;
    int status = invoke(direct, &candidate, 1, &timeout, sizeof(uint64_t));
    int error = errno;
    assert(status == 0 && candidate.revents == 0);
    assert(error == E2BIG && mask_restored());
    const char *timeout_result = timeout.tv_nsec == 0 ? "zero" : "retained";
    assert(timeout.tv_sec == 0 && timeout.tv_nsec == (direct ? 0 : 1000000));
    printf("%s expired timeout=%s stale-errno=E2BIG mask=restored\n", which, timeout_result);

    assert(write(tube[1], "L", 1) == 1);
    candidate.revents = 0;
    timeout = (struct timespec){ .tv_sec = 1, .tv_nsec = 0 };
    status = invoke(direct, &candidate, 1, &timeout, sizeof(uint64_t));
    assert(status == 1 && candidate.revents == POLLIN && mask_restored());
    assert(timeout.tv_sec == 0 || timeout.tv_sec == 1);
    assert(timeout.tv_nsec >= 0 && timeout.tv_nsec < 1000000000);
    assert(timeout.tv_sec == 0 || timeout.tv_nsec == 0);
    if (!direct)
        assert(timeout.tv_sec == 1 && timeout.tv_nsec == 0);
    char contents;
    assert(read(tube[0], &contents, 1) == 1 && contents == 'L');
    printf("%s ready event=POLLIN delivered=L mask=restored\n", which);

    timeout = (struct timespec){ .tv_sec = -1, .tv_nsec = 0 };
    errno = 0;
    status = invoke(direct, &candidate, 1, &timeout, sizeof(uint64_t));
    assert(status == -1 && errno == EINVAL && mask_restored());
    printf("%s invalid-timeout result=EINVAL mask=restored\n", which);

    if (direct) {
        timeout = (struct timespec){ .tv_sec = 0, .tv_nsec = 0 };
        assert(sizeof(sigset_t) != sizeof(uint64_t));
        errno = 0;
        status = invoke(1, &candidate, 1, &timeout, sizeof(sigset_t));
        assert(status == -1 && errno == EINVAL && mask_restored());
        printf("%s libc-mask-size=%zu kernel-mask-size=%zu result=EINVAL\n",
               which, sizeof(sigset_t), sizeof(uint64_t));
    }
    assert(close(tube[0]) == 0 && close(tube[1]) == 0);
}

int main(void) {
    sigset_t blocked;
    assert(sigemptyset(&blocked) == 0 && sigaddset(&blocked, SIGUSR1) == 0);
    assert(sigprocmask(SIG_BLOCK, &blocked, NULL) == 0);
    for (int run = 0; run < 5; ++run) {
        probe(0);
        probe(1);
    }
    return 0;
}
