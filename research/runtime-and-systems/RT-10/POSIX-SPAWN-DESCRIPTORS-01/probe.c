#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

enum { INHERITED = 80, CLOEXEC = 81, MAPPED = 82, ABSENT = 83 };

static void die(const char *operation) {
    perror(operation);
    exit(2);
}

static void require_zero(int status, const char *operation) {
    if (status != 0) {
        errno = status;
        die(operation);
    }
}

static void inspect(const char *mode) {
    for (int fd = INHERITED; fd <= ABSENT; ++fd) {
        int flags = fcntl(fd, F_GETFD);
        if (flags < 0) {
            if (errno != EBADF) {
                die("F_GETFD");
            }
            printf("%s fd %d closed\n", mode, fd);
            continue;
        }
        unsigned char byte;
        if (read(fd, &byte, 1) != 1) {
            die("read child descriptor");
        }
        printf("%s fd %d %s %u\n", mode, fd, flags & FD_CLOEXEC ? "cloexec" : "open",
               (unsigned)byte);
    }
    if (fflush(stdout) != 0) {
        die("flush child observations");
    }
}

static void collect(const char *mode, pid_t child, int source) {
    int status;
    if (waitpid(child, &status, 0) != child || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        die("wait for observed child");
    }
    off_t offset = lseek(source, 0, SEEK_CUR);
    if (offset < 0) {
        die("read parent offset");
    }
    printf("%s parent %lld\n", mode, (long long)offset);
    if (fflush(stdout) != 0) {
        die("flush parent observations");
    }
}

static void reset(int source) {
    if (lseek(source, 0, SEEK_SET) != 0) {
        die("reset shared offset");
    }
}

static void fork_probe(char *executable, char *mode, int source, int replace) {
    reset(source);
    pid_t child = fork();
    if (child < 0) {
        die("fork");
    }
    if (child == 0) {
        if (replace) {
            char *args[] = {executable, "--inspect", mode, NULL};
            execv(executable, args);
            die("execv");
        }
        inspect(mode);
        _exit(0);
    }
    collect(mode, child, source);
}

static void spawn_probe(char *executable, char *mode, int source,
                        posix_spawn_file_actions_t *actions, int expected_error) {
    reset(source);
    char *args[] = {executable, "--inspect", mode, NULL};
    pid_t child = -1;
    int result = posix_spawn(&child, executable, actions, NULL, args, environ);
    if (expected_error) {
        if (result != expected_error || child != -1) {
            require_zero(result, "unexpected posix_spawn result");
            die("unexpected child for refused spawn");
        }
        printf("%s spawn EBADF\n", mode);
        if (fflush(stdout) != 0) {
            die("flush refusal observations");
        }
        return;
    }
    require_zero(result, "posix_spawn");
    collect(mode, child, source);
}

int main(int argc, char *argv[]) {
    if (argc == 3 && strcmp(argv[1], "--inspect") == 0) {
        inspect(argv[2]);
        return 0;
    }
    if (argc != 2) {
        return 2;
    }
    int source = open(argv[1], O_RDONLY | O_CLOEXEC);
    if (source < 0 || dup2(source, INHERITED) != INHERITED ||
        fcntl(source, F_DUPFD_CLOEXEC, CLOEXEC) != CLOEXEC) {
        die("set up descriptor fixture");
    }

    fork_probe(argv[0], "fork-only", source, 0);
    fork_probe(argv[0], "fork-exec", source, 1);
    if (dup2(CLOEXEC, CLOEXEC) != CLOEXEC) {
        die("same-descriptor dup2");
    }
    fork_probe(argv[0], "raw-self-dup2-then-exec", source, 1);
    spawn_probe(argv[0], "spawn-default", source, NULL, 0);

    posix_spawn_file_actions_t actions;
    require_zero(posix_spawn_file_actions_init(&actions), "init map actions");
    require_zero(posix_spawn_file_actions_adddup2(&actions, CLOEXEC, MAPPED), "add map action");
    require_zero(posix_spawn_file_actions_addclose(&actions, CLOEXEC), "close original after map");
    require_zero(posix_spawn_file_actions_addclose(&actions, INHERITED), "close default inheritance");
    spawn_probe(argv[0], "spawn-map-then-close", source, &actions, 0);
    require_zero(posix_spawn_file_actions_destroy(&actions), "destroy map actions");

    require_zero(posix_spawn_file_actions_init(&actions), "init reverse actions");
    require_zero(posix_spawn_file_actions_addclose(&actions, CLOEXEC), "close original before map");
    require_zero(posix_spawn_file_actions_adddup2(&actions, CLOEXEC, MAPPED), "map closed source");
    spawn_probe(argv[0], "spawn-close-then-map", source, &actions, EBADF);
    require_zero(posix_spawn_file_actions_destroy(&actions), "destroy reverse actions");

    require_zero(posix_spawn_file_actions_init(&actions), "init self-map actions");
    require_zero(posix_spawn_file_actions_adddup2(&actions, CLOEXEC, CLOEXEC), "add self-map action");
    require_zero(posix_spawn_file_actions_addclose(&actions, INHERITED), "close inherited alias");
    spawn_probe(argv[0], "spawn-self-map", source, &actions, 0);
    require_zero(posix_spawn_file_actions_destroy(&actions), "destroy self-map actions");

    require_zero(posix_spawn_file_actions_init(&actions), "init missing-source actions");
    require_zero(posix_spawn_file_actions_adddup2(&actions, ABSENT, MAPPED), "add missing-source action");
    spawn_probe(argv[0], "spawn-missing-source", source, &actions, EBADF);
    require_zero(posix_spawn_file_actions_destroy(&actions), "destroy missing-source actions");

    if (close(CLOEXEC) < 0 || close(INHERITED) < 0 || close(source) < 0) {
        die("close fixture descriptors");
    }
    return 0;
}
