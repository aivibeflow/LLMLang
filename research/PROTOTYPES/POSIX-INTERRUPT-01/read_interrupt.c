/* Observe the difference between returning EINTR and restarting a pipe read. */
#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static pid_t child = -1;
static volatile sig_atomic_t notice_fd;

struct result {
    ssize_t transferred;
    int failure;
    unsigned char byte;
};

static void ensure(int condition, const char *step)
{
    if (!condition) {
        fprintf(stderr, "pipe interrupt fixture failed: %s\n", step);
        if (child > 0) {
            kill(child, SIGKILL);
            while (waitpid(child, NULL, 0) < 0 && errno == EINTR) {}
        }
        exit(EXIT_FAILURE);
    }
}

static void notify_signal(int sig)
{
    int saved = errno;
    const char notice = 'S';
    (void)sig;
    (void)write(notice_fd, &notice, 1);
    errno = saved;
}

static _Noreturn void run_reader(int input, int notice, int report, int restart, int system_call)
{
    struct sigaction action = {0};
    action.sa_handler = notify_signal;
    action.sa_flags = restart ? SA_RESTART : 0;
    notice_fd = notice;
    sigset_t signals;
    if (sigemptyset(&action.sa_mask) < 0 || sigaction(SIGUSR1, &action, NULL) < 0
        || sigemptyset(&signals) < 0 || sigaddset(&signals, SIGUSR1) < 0
        || sigprocmask(SIG_UNBLOCK, &signals, NULL) < 0)
        _exit(1);
    struct result result = {.byte = 0xE7};
    result.transferred = system_call ? syscall(SYS_read, input, &result.byte, 1)
                                     : read(input, &result.byte, 1);
    result.failure = result.transferred < 0 ? errno : 0;
    if (write(report, &result, sizeof result) != sizeof result)
        _exit(1);
    _exit(0);
}

static void wait_for_read(int fd)
{
    char path[64];
    snprintf(path, sizeof path, "/proc/%ld/syscall", (long)child);
    const struct timespec interval = {.tv_nsec = 1000000};
    for (int attempt = 0; attempt < 2000; ++attempt) {
        FILE *file = fopen(path, "r");
        ensure(file != NULL, "parent must be able to read child syscall from procfs");
        long operation;
        unsigned long argument;
        int fields = fscanf(file, "%ld %lx", &operation, &argument);
        ensure(!ferror(file), "read child syscall from procfs");
        fclose(file);
        if (fields == 2 && operation == SYS_read && argument == (unsigned long)fd)
            return;
        nanosleep(&interval, NULL);
    }
    ensure(0, "reader did not reach the expected syscall");
}

static void receive(int fd, void *buffer, size_t size)
{
    struct pollfd poll_result = {.fd = fd, .events = POLLIN};
    ensure(poll(&poll_result, 1, 2000) == 1 && (poll_result.revents & POLLIN),
           "reader did not send its observation");
    ensure(read(fd, buffer, size) == (ssize_t)size, "receive complete fixture record");
}

static void run(int restart, int system_call)
{
    int data[2], notice[2], report[2];
    ensure(pipe(data) == 0 && pipe(notice) == 0 && pipe(report) == 0, "create pipes");
    child = fork();
    ensure(child >= 0, "fork reader");
    if (child == 0) {
        close(data[1]);
        close(notice[0]);
        close(report[0]);
        run_reader(data[0], notice[1], report[1], restart, system_call);
    }

    close(data[0]);
    close(notice[1]);
    close(report[1]);
    wait_for_read(data[0]);
    ensure(kill(child, SIGUSR1) == 0, "signal the blocked child");
    char signaled;
    receive(notice[0], &signaled, 1);
    ensure(signaled == 'S', "handler acknowledgment");
    if (restart) {
        wait_for_read(data[0]);
        const unsigned char byte = 'R';
        ensure(write(data[1], &byte, 1) == 1, "send data to restarted read");
    }

    struct result observed;
    receive(report[0], &observed, sizeof observed);
    int status;
    pid_t expected = child;
    pid_t reaped = waitpid(expected, &status, 0);
    if (reaped == expected)
        child = -1;
    ensure(reaped == expected && WIFEXITED(status) && WEXITSTATUS(status) == 0, "reader exit");
    close(data[1]);
    close(notice[0]);
    close(report[0]);
    if (restart) {
        ensure(observed.transferred == 1 && observed.failure == 0 && observed.byte == 'R',
               "restarted read returned the supplied byte");
    } else {
        ensure(observed.transferred == -1 && observed.failure == EINTR && observed.byte == 0xE7,
               "interrupted read returned EINTR and left the output untouched");
    }
}

int main(void)
{
    for (int system_call = 0; system_call <= 1; ++system_call) {
        for (int restart = 0; restart <= 1; ++restart) {
            for (int iteration = 0; iteration < 20; ++iteration)
                run(restart, system_call);
            printf("%s restart=%d: 20 observations matched\n",
                   system_call ? "syscall" : "libc", restart);
        }
    }
}
