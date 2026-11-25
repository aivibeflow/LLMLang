#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/landlock.h>
#include <linux/seccomp.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <unistd.h>

static void require(int condition, const char *operation) {
    if (!condition) {
        perror(operation);
        exit(2);
    }
}

static int landlock_version(void) {
    return (int)syscall(SYS_landlock_create_ruleset, NULL, 0, LANDLOCK_CREATE_RULESET_VERSION);
}

#define ALLOW_SYSCALL(number) \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (number), 0, 1), \
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW)

static void restrict_to_worker_calls(void) {
    struct sock_filter instructions[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EACCES),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        ALLOW_SYSCALL(SYS_read),
        ALLOW_SYSCALL(SYS_write),
        ALLOW_SYSCALL(SYS_close),
        ALLOW_SYSCALL(SYS_exit),
        ALLOW_SYSCALL(SYS_exit_group),
        ALLOW_SYSCALL(SYS_rt_sigreturn),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EACCES),
    };
    const struct sock_fprog program = {
        .len = sizeof instructions / sizeof instructions[0],
        .filter = instructions,
    };
    require(prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == 0, "set no-new-privileges");
    require(prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program) == 0, "enforce seccomp worker profile");
}

static int readable_descriptor(int descriptor, char expected) {
    char observed = 0;
    ssize_t count = read(descriptor, &observed, 1);
    if (count == -1 && errno == EBADF) {
        return 0;
    }
    require(count == 1 && observed == expected, "read fixture descriptor");
    return 1;
}

static int openable(const char *path, int flags) {
    int descriptor = open(path, flags | O_CLOEXEC);
    if (descriptor < 0) {
        require(errno == EACCES, "open fixture path");
        return 0;
    }
    require(close(descriptor) == 0, "close fixture path");
    return 1;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        errno = 0;
        int abi = landlock_version();
        printf("%d %d\n", abi, errno);
        return 0;
    }
    if (argc != 4) {
        return 2;
    }
    setbuf(stdout, NULL);
    int permitted_fd = atoi(argv[2]);
    int synthetic_fd = atoi(argv[3]);
    if (strcmp(argv[1], "restricted") == 0) {
        restrict_to_worker_calls();
    }
    printf("public_env=%d\n", getenv("LLMLANG_FIXTURE_PUBLIC") != NULL);
    printf("fixture_private_env=%d\n", getenv("LLMLANG_FIXTURE_PRIVATE") != NULL);
    printf("public_fd=%d\n", readable_descriptor(permitted_fd, 'p'));
    printf("fixture_private_fd=%d\n", readable_descriptor(synthetic_fd, 's'));
    printf("public_path_read=%d\n", openable("public/input", O_RDONLY));
    printf("fixture_private_path_read=%d\n", openable("private/input", O_RDONLY));
    printf("public_path_write=%d\n", openable("public/input", O_WRONLY));
    return 0;
}
