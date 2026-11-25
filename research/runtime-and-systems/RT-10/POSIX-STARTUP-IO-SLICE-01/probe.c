#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

enum { child_input = 80, child_result = 81 };
extern char **environ;

static int child(const char *canary_argument)
{
    int canary = atoi(canary_argument);
    assert(fcntl(canary, F_GETFD) == -1 && errno == EBADF);
    char payload[16] = {0};
    char counts[16] = {0};
    int calls = 0;
    int filled = 0;
    for (;;) {
        assert(filled + 2 < (int)sizeof payload);
        ssize_t result = read(child_input, payload + filled, 2);
        assert(calls < (int)sizeof counts - 1);
        counts[calls++] = result < 0 ? 'e' : (char)('0' + result);
        if (result < 0) {
            int cause = errno;
            assert(dprintf(child_result, "io-error:%d;counts=%s;payload=%s", cause, counts, payload) > 0);
            return 12;
        }
        if (result == 0) {
            assert(dprintf(child_result, "eof;counts=%s;payload=%s", counts, payload) > 0);
            return 0;
        }
        filled += (int)result;
    }
}

static void assert_closed(int descriptor)
{
    assert(fcntl(descriptor, F_GETFD) == -1 && errno == EBADF);
}

static void parent(const char *program, const char *scenario, const char *path)
{
    int write_only = strcmp(scenario, "child-read-error") == 0;
    int reports[2];
    int source = open(path, (write_only ? O_WRONLY : O_RDONLY) | O_CLOEXEC);
    assert(source >= 0 && source < child_input);
    int canary = open(path, O_RDONLY | O_CLOEXEC);
    assert(canary >= 0 && canary < child_input);
    assert(pipe(reports) == 0 && reports[0] < child_input && reports[1] < child_input);
    for (int i = 0; i < 2; ++i)
        assert(fcntl(reports[i], F_SETFD, FD_CLOEXEC) == 0);
    assert_closed(child_input);
    assert_closed(child_result);

    off_t offset = strcmp(scenario, "progress") == 0 ? 1 : 0;
    assert(lseek(source, offset, SEEK_SET) == offset);
    posix_spawn_file_actions_t actions;
    assert(posix_spawn_file_actions_init(&actions) == 0);
    assert(posix_spawn_file_actions_adddup2(&actions, reports[1], child_result) == 0);
    if (strcmp(scenario, "invalid-map") == 0)
        assert(posix_spawn_file_actions_addclose(&actions, source) == 0);
    if (strcmp(scenario, "missing-map") != 0)
        assert(posix_spawn_file_actions_adddup2(&actions, source, child_input) == 0);

    char descriptor[24];
    assert(snprintf(descriptor, sizeof descriptor, "%d", canary) > 0);
    char *arguments[] = {(char *)program, "child", descriptor, NULL};
    const char *executable = strcmp(scenario, "missing-program") == 0 ? "./absent-fixture-program" : program;
    pid_t pid;
    int started = posix_spawn(&pid, executable, &actions, NULL, arguments, environ);
    assert(posix_spawn_file_actions_destroy(&actions) == 0);
    assert(close(reports[1]) == 0);

    int child_exit = -1;
    if (started == 0) {
        int wait_status;
        assert(waitpid(pid, &wait_status, 0) == pid && WIFEXITED(wait_status));
        child_exit = WEXITSTATUS(wait_status);
    }
    char report[96] = {0};
    ssize_t received;
    size_t filled = 0;
    while ((received = read(reports[0], report + filled, sizeof(report) - filled - 1)) > 0)
        filled += (size_t)received;
    assert(received == 0 && filled < sizeof(report) - 1);
    printf("spawn=%d\nchild_exit=%d\nreport=%s\nparent_offset=%lld\n",
           started, child_exit, report, (long long)lseek(source, 0, SEEK_CUR));
    assert(close(reports[0]) == 0);
    assert(close(source) == 0);
    assert(close(canary) == 0);
}

int main(int argc, char **argv)
{
    assert(argc == 3);
    if (strcmp(argv[1], "child") == 0)
        return child(argv[2]);
    parent(argv[0], argv[1], argv[2]);
    return 0;
}
