#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <unistd.h>

int main(void)
{
    int descriptors[2];
#if defined(PROBE_BASE)
    assert(pipe(descriptors) == 0);
    assert(fcntl(descriptors[0], F_GETFD) >= 0);
    printf("header=%ld\nruntime=%ld\n", (long)_POSIX_VERSION, sysconf(_SC_VERSION));
#elif defined(PROBE_PIPE2)
    assert(pipe2(descriptors, O_CLOEXEC | O_NONBLOCK) == 0);
    for (int end = 0; end < 2; ++end) {
        int close_flags = fcntl(descriptors[end], F_GETFD);
        int file_flags = fcntl(descriptors[end], F_GETFL);
        assert(close_flags >= 0 && (close_flags & FD_CLOEXEC));
        assert(file_flags >= 0 && (file_flags & O_NONBLOCK));
    }
    puts("both-close-on-exec-and-nonblocking");
#elif defined(PROBE_DUP3)
    assert(pipe(descriptors) == 0);
    int target = dup(descriptors[0]);
    assert(target >= 0);
    assert(dup3(descriptors[0], target, O_CLOEXEC) == target);
    assert(fcntl(target, F_GETFD) == FD_CLOEXEC);
    errno = 0;
    assert(dup3(descriptors[0], descriptors[0], O_CLOEXEC) == -1 && errno == EINVAL);
    assert(close(target) == 0);
    puts("close-on-exec-and-equal-fd-refused");
#elif defined(PROBE_CLOFORK)
#if !defined(O_CLOFORK) || !defined(FD_CLOFORK)
#error close-on-fork flags unavailable
#else
    assert(pipe2(descriptors, O_CLOFORK) == 0);
    for (int end = 0; end < 2; ++end) {
        int flags = fcntl(descriptors[end], F_GETFD);
        assert(flags >= 0 && (flags & FD_CLOFORK));
    }
    puts("both-close-on-fork");
#endif
#else
#error probe case required
#endif
    assert(close(descriptors[0]) == 0);
    assert(close(descriptors[1]) == 0);
    return 0;
}
