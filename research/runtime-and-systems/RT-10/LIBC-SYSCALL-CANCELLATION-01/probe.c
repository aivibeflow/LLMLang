#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

#if !defined(__x86_64__) || !defined(__linux__)
#error x86-64 Linux syscall ABI required
#endif

struct job {
    pthread_barrier_t start;
    pthread_barrier_t release;
    int reader;
    int raw;
    long read_result;
    char byte;
    int cleanup_called;
};

static void barrier_wait(pthread_barrier_t *barrier)
{
    int result = pthread_barrier_wait(barrier);
    assert(result == 0 || result == PTHREAD_BARRIER_SERIAL_THREAD);
}

static void record_cleanup(void *context)
{
    struct job *state = context;
    state->cleanup_called = 1;
}

static long read_syscall(int descriptor, char *byte)
{
    long result = SYS_read;
    __asm__ volatile("syscall"
                     : "+a"(result)
                     : "D"((long)descriptor), "S"(byte), "d"(1L)
                     : "rcx", "r11", "memory");
    return result;
}

static void *work(void *context)
{
    struct job *state = context;
    assert(pthread_setcanceltype(PTHREAD_CANCEL_DEFERRED, NULL) == 0);
    pthread_cleanup_push(record_cleanup, state);
    barrier_wait(&state->start);
    barrier_wait(&state->release);
    if (state->raw)
        state->read_result = read_syscall(state->reader, &state->byte);
    else
        state->read_result = read(state->reader, &state->byte, 1);
    pthread_testcancel();
    pthread_cleanup_pop(0);
    return context;
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    int descriptors[2];
    assert(pipe2(descriptors, O_NONBLOCK | O_CLOEXEC) == 0);
    struct job state = {
        .reader = descriptors[0],
        .raw = strcmp(argv[1], "syscall") == 0,
        .read_result = -99,
    };
    assert(pthread_barrier_init(&state.start, NULL, 2) == 0);
    assert(pthread_barrier_init(&state.release, NULL, 2) == 0);
    pthread_t worker;
    assert(pthread_create(&worker, NULL, work, &state) == 0);
    barrier_wait(&state.start);
    if (strcmp(argv[2], "pending") == 0)
        assert(pthread_cancel(worker) == 0);
    assert(write(descriptors[1], "x", 1) == 1);
    barrier_wait(&state.release);
    void *terminal;
    assert(pthread_join(worker, &terminal) == 0);
    assert(terminal == &state || terminal == PTHREAD_CANCELED);

    char pending_byte = 0;
    ssize_t pending_result = read(descriptors[0], &pending_byte, 1);
    assert((pending_result == -1 && errno == EAGAIN) ||
           (pending_result == 1 && pending_byte == 'x'));
    printf("terminal=%s\ncleanup=%d\nread_result=%ld\nread_byte=%d\nleftover=%ld\n",
           terminal == PTHREAD_CANCELED ? "cancelled" : "normal", state.cleanup_called,
           state.read_result, (int)state.byte, pending_result == 1 ? 1L : 0L);

    assert(pthread_barrier_destroy(&state.start) == 0);
    assert(pthread_barrier_destroy(&state.release) == 0);
    assert(close(descriptors[0]) == 0);
    assert(close(descriptors[1]) == 0);
    return 0;
}
