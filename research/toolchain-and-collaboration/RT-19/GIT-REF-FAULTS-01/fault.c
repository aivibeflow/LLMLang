#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

static bool ends_with(const char *path, const char *suffix)
{
    size_t length = strlen(path), tail = strlen(suffix);
    return length >= tail && strcmp(path + length - tail, suffix) == 0;
}

static const char *role_of_path(const char *path)
{
    const char *root = getenv("FIXTURE_ROOT");
    if (!root || strncmp(path, root, strlen(root)) || path[strlen(root)] != '/')
        return NULL;
    if (ends_with(path, "/refs/llmlang/fixture/alpha.lock"))
        return "alpha-lock";
    if (ends_with(path, "/refs/llmlang/fixture/beta.lock"))
        return "beta-lock";
    if (ends_with(path, "/reftable/tables.list.lock"))
        return "table-list-lock";
    if (strstr(path, "/reftable/") && strstr(path, ".temp."))
        return "table-temp";
    return NULL;
}

static const char *role_of_fd(int fd)
{
    char link[64], path[PATH_MAX];
    snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
    ssize_t length = readlink(link, path, sizeof(path) - 1);
    if (length < 0)
        return NULL;
    path[length] = '\0';
    return role_of_path(path);
}

static bool inject(const char *operation, const char *role)
{
    static unsigned matches;
    const char *log_path = getenv("FIXTURE_LOG");
    if (!role || !log_path)
        return false;
    int saved_errno = errno;
    const char *target_operation = getenv("FIXTURE_OPERATION");
    const char *target_role = getenv("FIXTURE_ROLE");
    const char *count = getenv("FIXTURE_OCCURRENCE");
    bool failed = target_operation && target_role && count &&
                  !strcmp(operation, target_operation) && !strcmp(role, target_role) &&
                  ++matches == strtoul(count, NULL, 10);
    char line[128];
    int size = snprintf(line, sizeof(line), "%s %s %s\n",
                        operation, role, failed ? "failed" : "observed");
    int log = open(log_path, O_WRONLY | O_APPEND | O_CREAT | O_CLOEXEC, 0600);
    if (log < 0)
        _exit(71);
    if (syscall(SYS_write, log, line, (size_t)size) != size)
        _exit(71);
    close(log);
    errno = failed ? (!strcmp(operation, "write") ? ENOSPC : EIO) : saved_errno;
    return failed;
}

ssize_t write(int fd, const void *buffer, size_t length)
{
    ssize_t (*real_write)(int, const void *, size_t) = dlsym(RTLD_NEXT, "write");
    if (inject("write", role_of_fd(fd)))
        return -1;
    return real_write(fd, buffer, length);
}

int fsync(int fd)
{
    int (*real_fsync)(int) = dlsym(RTLD_NEXT, "fsync");
    if (inject("fsync", role_of_fd(fd)))
        return -1;
    return real_fsync(fd);
}

int rename(const char *old_path, const char *new_path)
{
    int (*real_rename)(const char *, const char *) = dlsym(RTLD_NEXT, "rename");
    if (inject("rename", role_of_path(old_path)))
        return -1;
    return real_rename(old_path, new_path);
}
