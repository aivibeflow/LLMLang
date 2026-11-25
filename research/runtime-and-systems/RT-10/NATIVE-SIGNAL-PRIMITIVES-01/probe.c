#define _GNU_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static atomic_int acknowledge;

struct worker {
    int endpoint;
    int use_poll;
    atomic_long tid;
    long result;
    int error;
    char data;
};

static void received(int signal_number) {
    (void)signal_number;
    int saved = errno;
    ssize_t written = write(atomic_load_explicit(&acknowledge, memory_order_relaxed), "!", 1);
    (void)written;
    errno = saved;
}

static void *perform(void *argument) {
    struct worker *worker = argument;
    atomic_store(&worker->tid, syscall(SYS_gettid));
    errno = E2BIG;
    if (worker->use_poll) {
        struct pollfd entry = { .fd = worker->endpoint, .events = POLLIN };
        worker->result = poll(&entry, 1, -1);
    } else {
        worker->result = read(worker->endpoint, &worker->data, 1);
    }
    worker->error = errno;
    return NULL;
}

static void one_pause(void) {
    struct timespec delay = { .tv_nsec = 1000000L };
    nanosleep(&delay, NULL);
}

static int proc_syscall(long thread_id, long expected) {
    char filename[96];
    snprintf(filename, sizeof(filename), "/proc/self/task/%ld/syscall", thread_id);
    FILE *source = fopen(filename, "r");
    if (source == NULL)
        return 0;
    long call = -1;
    int present = fscanf(source, "%ld", &call);
    fclose(source);
    return present == 1 && call == expected;
}

static void wait_for_call(struct worker *worker, long expected) {
    for (int attempt = 0; attempt < 5000; ++attempt) {
        long thread_id = atomic_load(&worker->tid);
        if (thread_id > 0 && proc_syscall(thread_id, expected))
            return;
        one_pause();
    }
    fprintf(stderr, "fixture did not see worker blocked in syscall %ld\n", expected);
    assert(0);
}

static const char *named_error(int code) {
    switch (code) {
        case EINTR: return "EINTR";
        case E2BIG: return "E2BIG";
        case EAGAIN: return "EAGAIN";
        case EBADF: return "EBADF";
        case 0: return "zero";
        default: return "unexpected";
    }
}

static void signal_case(int use_poll, int restart) {
    int input[2], event[2];
    assert(pipe(input) == 0 && pipe(event) == 0);
    assert(atomic_is_lock_free(&acknowledge));
    atomic_store_explicit(&acknowledge, event[1], memory_order_relaxed);
    struct sigaction handler = {0};
    handler.sa_handler = received;
    handler.sa_flags = restart ? SA_RESTART : 0;
    assert(sigemptyset(&handler.sa_mask) == 0);
    struct sigaction original;
    assert(sigaction(SIGUSR1, &handler, &original) == 0);

    struct worker operation = { .endpoint = input[0], .use_poll = use_poll };
    pthread_t thread;
    assert(pthread_create(&thread, NULL, perform, &operation) == 0);
    wait_for_call(&operation, use_poll ? SYS_poll : SYS_read);
    assert(pthread_kill(thread, SIGUSR1) == 0);
    struct pollfd signal_arrived = { .fd = event[0], .events = POLLIN };
    assert(poll(&signal_arrived, 1, 5000) == 1);
    char done;
    assert(read(event[0], &done, 1) == 1 && done == '!');

    int resumed = !use_poll && restart;
    if (resumed) {
        wait_for_call(&operation, SYS_read);
        assert(write(input[1], "Q", 1) == 1);
    }
    assert(pthread_join(thread, NULL) == 0);

    int preserved = 0;
    if (!resumed) {
        assert(write(input[1], "Q", 1) == 1);
        assert(read(input[0], &done, 1) == 1 && done == 'Q');
        preserved = 1;
    }
    printf("%s %d %ld %s %d %d\n", use_poll ? "poll" : "read", restart,
           operation.result, named_error(operation.error), (unsigned char)operation.data, preserved);
    assert(sigaction(SIGUSR1, &original, NULL) == 0);
    assert(close(event[0]) == 0 && close(event[1]) == 0);
    assert(close(input[0]) == 0 && close(input[1]) == 0);
}

static void immediate_cases(void) {
    int input[2];
    char item;
    assert(pipe2(input, O_NONBLOCK) == 0);
    errno = E2BIG;
    ssize_t result = read(input[0], &item, 1);
    printf("nonblocking %ld %s\n", (long)result, named_error(errno));
    assert(close(input[1]) == 0);
    errno = E2BIG;
    result = read(input[0], &item, 1);
    printf("eof %ld %s\n", (long)result, named_error(errno));
    assert(close(input[0]) == 0);
    errno = E2BIG;
    result = read(-1, &item, 1);
    printf("invalid %ld %s\n", (long)result, named_error(errno));
}

int main(void) {
    for (int count = 0; count < 5; ++count) {
        for (int type = 0; type < 2; ++type)
            for (int restart = 0; restart < 2; ++restart)
                signal_case(type, restart);
        immediate_cases();
    }
    return 0;
}
