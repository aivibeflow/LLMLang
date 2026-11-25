#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void require(int accepted, const char *label) {
    if (!accepted) {
        perror(label);
        exit(EXIT_FAILURE);
    }
}

static void make_file(const char *path, const char *payload) {
    int fd = open(path, O_WRONLY | O_CREAT | O_EXCL, 0600);
    require(fd >= 0, "open create");
    size_t size = strlen(payload);
    require(write(fd, payload, size) == (ssize_t)size, "write fixture");
    require(close(fd) == 0, "close writer");
}

static int opened(const char *path) {
    int fd = open(path, O_RDONLY);
    require(fd >= 0, "open reader");
    return fd;
}

static char take(int fd) {
    char value = 0;
    ssize_t n = read(fd, &value, 1);
    require(n >= 0, "read");
    return n == 0 ? '-' : value;
}

static struct stat details(int fd) {
    struct stat result;
    require(fstat(fd, &result) == 0, "fstat");
    return result;
}

static int same_object(int a, int b) {
    struct stat left = details(a);
    struct stat right = details(b);
    return left.st_dev == right.st_dev && left.st_ino == right.st_ino;
}

int main(void) {
    make_file("current", "ABC");
    require(link("current", "alias") == 0, "add hard link");
    int first = opened("current");
    int duplicate = dup(first);
    require(duplicate >= 0, "dup");
    int independent = opened("current");

    printf("first_read=%c\n", take(first));
    printf("duplicate_read=%c\n", take(duplicate));
    printf("independent_read=%c\n", take(independent));
    char explicit_offset = 0;
    require(pread(duplicate, &explicit_offset, 1, 0) == 1, "pread");
    printf("pread_at_zero=%c\n", explicit_offset);
    printf("first_offset_after_pread=%lld\n", (long long)lseek(first, 0, SEEK_CUR));
    printf("independent_offset=%lld\n", (long long)lseek(independent, 0, SEEK_CUR));

    make_file("next", "XYZ");
    require(rename("next", "current") == 0, "replace pathname");
    int fresh = opened("current");
    int via_alias = opened("alias");
    printf("alias_keeps_first_object=%d\n", same_object(first, via_alias));
    printf("current_keeps_first_object=%d\n", same_object(first, fresh));
    printf("fresh_read=%c\n", take(fresh));
    printf("alias_read=%c\n", take(via_alias));
    printf("first_links_after_rename=%llu\n", (unsigned long long)details(first).st_nlink);

    require(unlink("alias") == 0, "unlink alias");
    require(unlink("current") == 0, "unlink current");
    int missing = open("current", O_RDONLY);
    printf("current_absent=%d\n", missing < 0 && errno == ENOENT);
    require(missing < 0, "unexpected current object");
    printf("first_links_after_unlink=%llu\n", (unsigned long long)details(first).st_nlink);
    printf("fresh_links_after_unlink=%llu\n", (unsigned long long)details(fresh).st_nlink);
    printf("duplicate_read_after_unlink=%c\n", take(duplicate));
    printf("fresh_read_after_unlink=%c\n", take(fresh));

    require(dup2(fresh, first) == first, "replace descriptor slot");
    printf("replaced_slot_now_points_at_fresh=%d\n", same_object(first, fresh));
    printf("duplicate_remains_on_original=%d\n", same_object(duplicate, independent));
    printf("remaining_fresh_read_via_replaced_slot=%c\n", take(first));
    printf("fresh_now_at_eof=%d\n", take(fresh) == '-');
    printf("independent_still_reads_original=%c\n", take(independent));

    require(close(first) == 0, "close first");
    require(close(duplicate) == 0, "close duplicate");
    require(close(independent) == 0, "close independent");
    require(close(fresh) == 0, "close fresh");
    require(close(via_alias) == 0, "close alias");
    return 0;
}
