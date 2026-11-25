#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <unistd.h>

static const char absent[] = "./absent-error-fixture";

struct thread_case {
    pthread_barrier_t *barrier;
    int kind;
    int observed;
};

static void wait_at(pthread_barrier_t *barrier)
{
    int result = pthread_barrier_wait(barrier);
    assert(result == 0 || result == PTHREAD_BARRIER_SERIAL_THREAD);
}

static void *thread_error(void *argument)
{
    struct thread_case *chosen = argument;
    if (chosen->kind == 0) {
        char buffer;
        assert(read(-1, &buffer, 1) == -1);
    } else {
        assert(open(absent, O_RDONLY) == -1);
    }
    wait_at(chosen->barrier);
    chosen->observed = errno;
    return NULL;
}

int main(void)
{
    pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;
    errno = EINTR;
    int first = pthread_mutex_trylock(&mutex);
    int after_first = errno;
    int busy = pthread_mutex_trylock(&mutex);
    int after_busy = errno;
    assert(first == 0 && busy == EBUSY);
    assert(pthread_mutex_unlock(&mutex) == 0);
    assert(pthread_mutex_destroy(&mutex) == 0);
    printf("trylock-success=%d:%d\ntrylock-busy=%d:%d\n", first, after_first, busy, after_busy);

    int data[2];
    assert(pipe(data) == 0 && write(data[1], "x", 1) == 1);
    char byte = 0;
    errno = ENOSPC;
    ssize_t succeeded = read(data[0], &byte, 1);
    int stale = errno;
    assert(succeeded == 1 && byte == 'x');
    assert(close(data[0]) == 0 && close(data[1]) == 0);
    printf("successful-read=%ld:%d:%d\n", (long)succeeded, stale, (int)byte);

    ssize_t failed = read(-1, &byte, 1);
    int captured = errno;
    assert(failed == -1 && open(absent, O_RDONLY) == -1);
    int delayed = errno;
    printf("failed-read=%ld:%d:%d\n", (long)failed, captured, delayed);

    pthread_barrier_t barrier;
    assert(pthread_barrier_init(&barrier, NULL, 2) == 0);
    struct thread_case cases[] = {{&barrier, 0, 0}, {&barrier, 1, 0}};
    pthread_t threads[2];
    for (int i = 0; i < 2; ++i)
        assert(pthread_create(&threads[i], NULL, thread_error, &cases[i]) == 0);
    for (int i = 0; i < 2; ++i)
        assert(pthread_join(threads[i], NULL) == 0);
    assert(pthread_barrier_destroy(&barrier) == 0);
    printf("reader-thread=%d\nopen-thread=%d\n", cases[0].observed, cases[1].observed);
    return 0;
}
