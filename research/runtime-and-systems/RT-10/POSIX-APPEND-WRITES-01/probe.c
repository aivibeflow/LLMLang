#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/uio.h>
#include <unistd.h>

#if !defined(__x86_64__) || !defined(__linux__)
#error This raw syscall adapter is scoped to Linux x86-64
#endif

enum { LINUX_RWF_APPEND = 0x10, LINUX_RWF_NOAPPEND = 0x20 };
#ifdef RWF_NOAPPEND
_Static_assert(RWF_NOAPPEND == LINUX_RWF_NOAPPEND, "libc header disagrees with Linux flag");
#endif

enum operation { POSITIONAL, VECTOR, VECTOR_IGNORE_APPEND, VECTOR_FORCE_APPEND, VECTOR_CURSOR };

struct scenario {
    const char *name;
    enum operation method;
    int initial_append;
    int alias_append;
};

static void require(int okay, const char *label)
{
    if (!okay) {
        perror(label);
        exit(1);
    }
}

static int append_enabled(int fd)
{
    int flags = fcntl(fd, F_GETFL);
    require(flags >= 0, "F_GETFL");
    return (flags & O_APPEND) != 0;
}

static long raw_vector(int fd, long offset, unsigned long flags)
{
    char byte = 'Z';
    struct iovec vector = { .iov_base = &byte, .iov_len = 1 };
    return syscall(SYS_pwritev2, fd, &vector, 1UL, (unsigned long)offset, 0UL, flags);
}

static void test(const struct scenario *test_case, int memory_file)
{
    char path[64] = "target";
    int seed = memory_file ? (int)syscall(SYS_memfd_create, "target", 0U)
                           : open(path, O_CREAT | O_EXCL | O_WRONLY, 0600);
    if (memory_file && seed >= 0)
        require(snprintf(path, sizeof(path), "/proc/self/fd/%d", seed) > 0, "memfd path");
    require(seed >= 0, "seed open");
    require(write(seed, "ABCD", 4) == 4, "seed write");

    int fd = open(path, O_RDWR | (test_case->initial_append ? O_APPEND : 0));
    require(fd >= 0, "primary open");
    int alias = dup(fd);
    require(alias >= 0, "dup");
    int observer = open(path, O_RDWR | (test_case->initial_append ? O_APPEND : 0));
    require(observer >= 0, "observer open");
    require(close(seed) == 0, "close seed");
    require(lseek(fd, 2, SEEK_SET) == 2, "set shared offset");
    require(lseek(observer, 3, SEEK_SET) == 3, "set independent offset");
    if (test_case->alias_append >= 0) {
        int flags = fcntl(alias, F_GETFL);
        require(flags >= 0, "alias F_GETFL");
        int replacement = test_case->alias_append ? (flags | O_APPEND) : (flags & ~O_APPEND);
        require(fcntl(alias, F_SETFL, replacement) == 0, "alias F_SETFL");
    }

    struct statfs filesystem;
    require(fstatfs(fd, &filesystem) == 0, "fstatfs");
    long result;
    errno = 0;
    switch (test_case->method) {
    case POSITIONAL:
        result = pwrite(fd, "Z", 1, 1);
        break;
    case VECTOR:
        result = raw_vector(fd, 1, 0);
        break;
    case VECTOR_IGNORE_APPEND:
        result = raw_vector(fd, 1, LINUX_RWF_NOAPPEND);
        break;
    case VECTOR_FORCE_APPEND:
        result = raw_vector(fd, 1, LINUX_RWF_APPEND);
        break;
    case VECTOR_CURSOR:
        result = raw_vector(fd, -1, LINUX_RWF_APPEND);
        break;
    default:
        abort();
    }
    int error = result < 0 ? errno : 0;
    char content[8] = {0};
    ssize_t bytes = pread(observer, content, sizeof(content) - 1, 0);
    require(bytes >= 0, "observe content");
    long primary_offset = (long)lseek(fd, 0, SEEK_CUR);
    long alias_offset = (long)lseek(alias, 0, SEEK_CUR);
    long independent_offset = (long)lseek(observer, 0, SEEK_CUR);
    require(primary_offset >= 0 && alias_offset >= 0 && independent_offset >= 0, "offset observations");
    printf("%s,%ld,%d,%s,%ld,%ld,%ld,%d,%d,%d,%lx\n", test_case->name, result, error, content,
           primary_offset, alias_offset, independent_offset,
           append_enabled(fd), append_enabled(alias), append_enabled(observer),
           (unsigned long)filesystem.f_type);

    require(close(observer) == 0, "close observer");
    require(close(alias) == 0, "close alias");
    require(close(fd) == 0, "close primary");
    if (!memory_file)
        require(unlink(path) == 0, "unlink fixture file");
}

int main(int argc, char **argv)
{
    int memory_file = argc == 2 && strcmp(argv[1], "memfd") == 0;
    if (argc != 1 && !memory_file)
        return 2;
    static const struct scenario cases[] = {
        {"pwrite-plain", POSITIONAL, 0, -1},
        {"pwrite-append", POSITIONAL, 1, -1},
        {"vector-plain", VECTOR, 0, -1},
        {"vector-append", VECTOR, 1, -1},
        {"vector-noappend-plain", VECTOR_IGNORE_APPEND, 0, -1},
        {"vector-noappend-append", VECTOR_IGNORE_APPEND, 1, -1},
        {"vector-force-append", VECTOR_FORCE_APPEND, 0, -1},
        {"vector-append-cursor", VECTOR_CURSOR, 0, -1},
        {"clear-through-alias", POSITIONAL, 1, 0},
        {"set-through-alias", POSITIONAL, 0, 1},
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(*cases); ++i)
        test(&cases[i], memory_file);
    return 0;
}
